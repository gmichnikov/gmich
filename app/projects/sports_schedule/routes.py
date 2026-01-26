import asyncio
import json

from flask import Blueprint, render_template, request, jsonify, current_app, Response, stream_with_context
from flask_login import login_required, current_user
from google.adk.runners import InMemoryRunner
from google.genai import types as genai_types

from app.utils.logging import log_project_visit
from app.projects.sports_schedule.agent import sports_agent

sports_schedule_bp = Blueprint('sports_schedule', __name__,
                               url_prefix='/sports-schedule',
                               template_folder='templates',
                               static_folder='static',
                               static_url_path='/sports-schedule/static')

# Create a runner for the agent
runner = InMemoryRunner(agent=sports_agent, app_name=sports_agent.name)


@sports_schedule_bp.route('/')
@login_required
def index():
    """Main page."""
    log_project_visit('sports_schedule', 'Sports Schedule')
    return render_template('sports_schedule/index.html')


@sports_schedule_bp.route('/ask', methods=['POST'])
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
    app_name = sports_agent.name

    def generate():
        # Use a queue to communicate between the async world and the sync generator
        import queue
        import threading
        
        q = queue.Queue()

        def run_async_loop():
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
                                text = "".join([p.text for p in event.content.parts if hasattr(p, 'text') and p.text])
                                if text:
                                    payload['type'] = 'text'
                                    payload['text'] = text
                        
                        if payload:
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
