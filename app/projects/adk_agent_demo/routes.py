import asyncio
import json

from flask import Blueprint, render_template, request, jsonify, current_app, Response, stream_with_context
from flask_login import login_required, current_user
from google.adk.runners import InMemoryRunner
from google.genai import types as genai_types

from app.utils.logging import log_project_visit
from app.projects.adk_agent_demo.agent import adk_agent

adk_agent_demo_bp = Blueprint('adk_agent_demo', __name__,
                               url_prefix='/adk-agent-demo',
                               template_folder='templates',
                               static_folder='static',
                               static_url_path='/adk-agent-demo/static')

# Create a runner for the agent
runner = InMemoryRunner(agent=adk_agent, app_name=adk_agent.name)


@adk_agent_demo_bp.route('/')
@login_required
def index():
    """Main page."""
    log_project_visit('adk_agent_demo', 'ADK Agent Demo')
    return render_template('adk_agent_demo/index.html', credits=current_user.credits)


@adk_agent_demo_bp.route('/ask', methods=['POST'])
@login_required
def ask_agent():
    """Send a message to the agent and get a streaming response."""
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'No message provided'}), 400

    message = data['message'].strip()
    if not message:
        return jsonify({'error': 'Message cannot be empty'}), 400

    user_id = str(current_user.id)
    session_id = f"session_{current_user.id}"
    app_name = adk_agent.name
    
    # 1. Deduct credit upfront in the main request context
    if current_user.credits < 1:
        return jsonify({'error': 'Insufficient credits'}), 400

    from app import db
    from app.models import LogEntry
    
    current_user.credits -= 1
    log = LogEntry(
        actor_id=current_user.id,
        project='adk_agent_demo',
        category='credit_use',
        description=f"Used 1 credit for ADK Agent Demo. Remaining: {current_user.credits}"
    )
    db.session.add(log)
    db.session.commit()

    # Capture state for generator/thread
    remaining_credits = current_user.credits
    app = current_app._get_current_object()

    def generate():
        # Use a queue to communicate between the async world and the sync generator
        import queue
        import threading
        
        q = queue.Queue()

        def run_async_loop():
            with app.app_context():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                async def run_it():
                    try:
                        # Ensure session exists
                        session = None
                        try:
                            session = await runner.session_service.get_session(
                                app_name=runner.app_name,
                                user_id=user_id,
                                session_id=session_id
                            )
                        except:
                            pass

                        if not session:
                            await runner.session_service.create_session(
                                app_name=runner.app_name,
                                user_id=user_id,
                                session_id=session_id
                            )

                        user_message = genai_types.Content(
                            role="user",
                            parts=[genai_types.Part(text=message)]
                        )

                        async for event in runner.run_async(
                            user_id=user_id,
                            session_id=session_id,
                            new_message=user_message
                        ):
                            payload = {}
                            # Handle tool calls
                            func_calls = event.get_function_calls()
                            if func_calls:
                                payload['type'] = 'tool_call'
                                payload['tool_calls'] = [{'name': fc.name, 'args': fc.args} for fc in func_calls]
                            else:
                                func_responses = event.get_function_responses()
                                if func_responses:
                                    payload['type'] = 'tool_response'
                                    payload['tool_responses'] = [{'name': fr.name, 'response': fr.response} for fr in func_responses]
                                elif event.content and event.content.parts:
                                    text_parts = []
                                    for p in event.content.parts:
                                        if hasattr(p, 'thought') and p.thought and p.text:
                                            q.put(f"data: {json.dumps({'type': 'thought', 'text': p.text, 'agent': event.author})}\n\n")
                                        elif hasattr(p, 'text') and p.text:
                                            text_parts.append(p.text)
                                    
                                    text = "".join(text_parts)
                                    if text:
                                        payload['type'] = 'text'
                                        payload['text'] = text
                            
                            if payload:
                                payload['agent'] = event.author
                                # Include remaining credits in the first chunk
                                if not hasattr(generate, 'credits_sent'):
                                    payload['remaining_credits'] = remaining_credits
                                    generate.credits_sent = True
                                q.put(f"data: {json.dumps(payload)}\n\n")
                                
                    except Exception as e:
                        q.put(f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n")
                    finally:
                        q.put(None) # Signal end

            loop.run_until_complete(run_it())
            loop.close()

        # Start the async loop in a separate thread
        threading.Thread(target=run_async_loop).start()

        # Yield from the queue
        while True:
            item = q.get()
            if item is None:
                break
            yield item

    return Response(stream_with_context(generate()), mimetype='text/event-stream')
