import asyncio

from flask import Blueprint, render_template, request, jsonify, current_app
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


async def run_agent(user_id: str, session_id: str, message: str) -> str:
    """Run the agent and return the response text."""
    # Ensure session exists
    app_name = sports_agent.name
    print(f"ADK DEBUG: Checking session for user_id={user_id}, session_id={session_id}, app_name={app_name}", flush=True)
    try:
        session = await runner.session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id
        )
        print(f"ADK DEBUG: Found existing session: {session.id}", flush=True)
    except Exception as e:
        print(f"ADK DEBUG: Session not found, creating one. Error was: {e}", flush=True)
        session = await runner.session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id
        )
        print(f"ADK DEBUG: Created new session: {session.id}", flush=True)

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=message)]
    )

    response_text = ""
    print(f"ADK DEBUG: Calling run_async with session_id={session_id}", flush=True)
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_message
    ):
        print(f"ADK DEBUG: Event received: {type(event)}", flush=True)
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    response_text = part.text

    return response_text


@sports_schedule_bp.route('/')
@login_required
def index():
    """Main page."""
    log_project_visit('sports_schedule', 'Sports Schedule')
    return render_template('sports_schedule/index.html')


@sports_schedule_bp.route('/ask', methods=['POST'])
@login_required
def ask_agent():
    """Send a message to the agent and get a response."""
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'No message provided'}), 400

    message = data['message'].strip()
    if not message:
        return jsonify({'error': 'Message cannot be empty'}), 400

    user_id = str(current_user.id)
    session_id = f"session_{current_user.id}"

    try:
        response = asyncio.run(run_agent(user_id, session_id, message))
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
