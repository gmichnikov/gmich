from flask import Blueprint, render_template
from flask_login import login_required
from app.utils.logging import log_project_visit

chatbot_bp = Blueprint('chatbot', __name__,
                       template_folder='templates',
                       static_folder='static')


@chatbot_bp.route('/')
@login_required
def index():
    """Display the chatbot interface"""
    log_project_visit('chatbot', 'Chatbot')
    return render_template('chatbot/chat.html')

# TODO: Add API routes for chat functionality

