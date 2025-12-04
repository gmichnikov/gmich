from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db, csrf
from app.models import LogEntry
from app.projects.chatbot.models import ChatMessage
from app.projects.chatbot.greg import GREG_CONTEXT
from app.utils.logging import log_project_visit
from uuid import uuid4
import os
from openai import OpenAI

chatbot_bp = Blueprint('chatbot', __name__,
                       template_folder='templates',
                       static_folder='static')


@chatbot_bp.route('/')
@login_required
def index():
    """Display the chatbot interface"""
    log_project_visit('chatbot', 'Greg-Bot')
    return render_template('chatbot/chat.html')


@chatbot_bp.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    """Get list of user's conversations"""
    conversations = db.session.query(
        ChatMessage.conversation_id,
        db.func.min(ChatMessage.timestamp).label('started')
    ).filter(
        ChatMessage.user_id == current_user.id
    ).group_by(
        ChatMessage.conversation_id
    ).order_by(
        db.desc('started')
    ).all()

    result = []
    for conv in conversations:
        # Get the first user message as the title
        first_message = db.session.query(ChatMessage.content).filter(
            ChatMessage.conversation_id == conv.conversation_id,
            ChatMessage.is_user == True
        ).order_by(ChatMessage.timestamp).first()
        
        title = first_message[0][:30] + "..." if first_message else "New conversation"
        
        result.append({
            'id': conv.conversation_id,
            'started': conv.started.isoformat(),
            'title': title
        })

    return jsonify(result)


@chatbot_bp.route('/api/messages/<conversation_id>', methods=['GET'])
@login_required
def get_messages(conversation_id):
    """Get messages for a specific conversation"""
    messages = ChatMessage.query.filter(
        ChatMessage.user_id == current_user.id,
        ChatMessage.conversation_id == conversation_id
    ).order_by(
        ChatMessage.timestamp
    ).all()

    return jsonify([msg.to_dict() for msg in messages])


@chatbot_bp.route('/api/messages', methods=['POST'])
@csrf.exempt
@login_required
def send_message():
    """Process a new message from the user"""
    data = request.json
    user_message = data.get('message', '').strip()
    conversation_id = data.get('conversation_id')

    # Create a new conversation if needed
    if not conversation_id:
        conversation_id = str(uuid4())
    else:
        # Validate existing conversation belongs to user
        message_count = ChatMessage.query.filter(
            ChatMessage.user_id == current_user.id,
            ChatMessage.conversation_id == conversation_id
        ).count()

        if message_count == 0:
            return jsonify({'error': 'Invalid conversation ID'}), 403

    # Save the user message
    user_chat_message = ChatMessage(
        user_id=current_user.id,
        conversation_id=conversation_id,
        content=user_message,
        is_user=True
    )
    db.session.add(user_chat_message)

    # Log the user message
    log_entry = LogEntry(
        actor_id=current_user.id,
        category='Chat Message',
        description=f"User sent message in conversation {conversation_id}",
        project='chatbot'
    )
    db.session.add(log_entry)
    db.session.commit()

    # Get bot response
    bot_response = generate_bot_response(user_message, conversation_id, current_user.id)

    # Save the bot response
    bot_chat_message = ChatMessage(
        user_id=current_user.id,
        conversation_id=conversation_id,
        content=bot_response,
        is_user=False
    )
    db.session.add(bot_chat_message)
    db.session.commit()

    return jsonify({
        'user_message': user_chat_message.to_dict(),
        'bot_message': bot_chat_message.to_dict(),
        'conversation_id': conversation_id
    })


@chatbot_bp.route('/api/conversations/<conversation_id>', methods=['DELETE'])
@csrf.exempt
@login_required
def delete_conversation(conversation_id):
    """Delete a specific conversation and all its messages"""
    try:
        ChatMessage.query.filter_by(
            user_id=current_user.id,
            conversation_id=conversation_id
        ).delete()

        db.session.commit()

        return jsonify({'status': 'success'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


def generate_bot_response(user_message, conversation_id, user_id):
    """
    Generate a response from the chatbot using OpenAI's API,
    including the full conversation history.
    """
    try:
        API_KEY = os.getenv('OPENAI_API_KEY')
        if not API_KEY:
            raise ValueError("OpenAI API key not found in environment variables")

        # Get the conversation history
        messages = ChatMessage.query.filter(
            ChatMessage.user_id == user_id,
            ChatMessage.conversation_id == conversation_id
        ).order_by(
            ChatMessage.timestamp
        ).all()

        system_content = f"""You are Greg-Bot, a helpful and friendly assistant who shares information about Greg Michnikov. Respond fairly briefly. Your response absolutely must be in plain text -- any use of markdown will look terrible so please don't do it.

When creating bullet points:
1. Always use a full line break (\\n) before each bullet point
2. Use simple dashes or asterisks followed by a space for bullets
3. Format like this:

- First bullet point
- Second bullet point
- Third bullet point

Keep responses concise. Never use markdown formatting.

{GREG_CONTEXT}"""

        # Format messages for the OpenAI API
        formatted_messages = [
            {"role": "system", "content": system_content}
        ]

        # Add conversation history
        for msg in messages:
            if msg.is_user:
                formatted_messages.append({"role": "user", "content": msg.content})
            else:
                formatted_messages.append({"role": "assistant", "content": msg.content})

        # Add the current user message
        formatted_messages.append({"role": "user", "content": user_message})

        client = OpenAI(api_key=API_KEY)

        completion = client.chat.completions.create(
            model="gpt-5-nano",
            messages=formatted_messages,
            max_completion_tokens=1000
        )

        return completion.choices[0].message.content

    except Exception as e:
        current_app.logger.error(f"OpenAI API error: {str(e)}")
        return "I apologize, but I'm having trouble generating a response right now."
