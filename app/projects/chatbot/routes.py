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
    return render_template('chatbot/chat.html', credits=current_user.credits)


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
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        conversation_id = data.get('conversation_id')

        # Check if user has sufficient credits
        if current_user.credits < 1:
            return jsonify({'error': 'Insufficient credits'}), 400

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
            category='Send',
            description=f"Sent message in conversation {conversation_id[:8]}",
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

        # Deduct credits after successful response
        current_user.credits -= 1

        # Log credit usage
        credit_log = LogEntry(
            project='chatbot',
            category='Credit Usage',
            actor_id=current_user.id,
            description=f"Used 1 credit for message in conversation {conversation_id[:8]}. Remaining: {current_user.credits}"
        )
        db.session.add(credit_log)
        db.session.commit()

        return jsonify({
            'user_message': user_chat_message.to_dict(),
            'bot_message': bot_chat_message.to_dict(),
            'conversation_id': conversation_id,
            'remaining_credits': current_user.credits
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in send_message: {str(e)}", exc_info=True)
        return jsonify({'error': 'An error occurred while processing your message'}), 500


@chatbot_bp.route('/api/conversations/<conversation_id>', methods=['DELETE'])
@csrf.exempt
@login_required
def delete_conversation(conversation_id):
    """Delete a specific conversation and all its messages"""
    try:
        # Count messages before deletion for logging
        message_count = ChatMessage.query.filter_by(
            user_id=current_user.id,
            conversation_id=conversation_id
        ).count()

        ChatMessage.query.filter_by(
            user_id=current_user.id,
            conversation_id=conversation_id
        ).delete()

        # Log the action
        log_entry = LogEntry(
            actor_id=current_user.id,
            category='Delete',
            description=f"Deleted conversation {conversation_id[:8]} ({message_count} messages)",
            project='chatbot'
        )
        db.session.add(log_entry)
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

        model = "gpt-5-mini"
        completion = client.chat.completions.create(
            model=model,
            messages=formatted_messages,
            reasoning_effort="minimal",
            max_completion_tokens=10000
        )

        response_content = completion.choices[0].message.content
        
        # Log if response is empty
        if not response_content:
            current_app.logger.warning(f"OpenAI returned empty response. Finish reason: {completion.choices[0].finish_reason}")
            return "I apologize, but I received an empty response. Please try again."
        
        # Log the API response with token usage
        log_entry = LogEntry(
            actor_id=user_id,
            category='Received Response',
            description=f"Conv {conversation_id[:8]} | Model: {model} | Prompt: {completion.usage.prompt_tokens}t | Response: {completion.usage.completion_tokens}t | Total: {completion.usage.total_tokens}t | Finish: {completion.choices[0].finish_reason}",
            project='chatbot'
        )
        db.session.add(log_entry)
        db.session.commit()
        
        return response_content

    except Exception as e:
        current_app.logger.error(f"OpenAI API error: {str(e)}")
        return "I apologize, but I'm having trouble generating a response right now."
