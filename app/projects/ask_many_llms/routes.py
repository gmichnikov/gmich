"""
Ask Many LLMs - Routes
Handles asking questions to multiple LLMs and viewing responses
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import LogEntry
from app.forms import AskManyLLMsForm
from app.projects.ask_many_llms.models import LLMQuestion, LLMResponse
from app.projects.ask_many_llms.services.llm_service import LLMService

bp = Blueprint('ask_many_llms', __name__, 
               url_prefix='/ask-many-llms',
               template_folder='templates',
               static_folder='static')

@bp.route('/')
@login_required
def index():
    """Redirect to ask question page"""
    return redirect(url_for('ask_many_llms.ask_question'))
llm_service = LLMService()

@bp.route('/api/create-question', methods=['POST'])
@login_required
def api_create_question():
    """Create a new question and deduct credits"""
    try:
        content = request.json.get('content')
        models = request.json.get('models', [])
        
        if not content or not models:
            return jsonify({'error': 'Missing content or models'}), 400
        
        if len(models) > 5:
            return jsonify({'error': 'Maximum 5 models allowed'}), 400
            
        if current_user.credits < 1:
            return jsonify({'error': 'Insufficient credits'}), 400
        
        # Create the question
        question = LLMQuestion(
            content=content,
            user_id=current_user.id
        )
        db.session.add(question)
        
        # Deduct credits immediately
        current_user.credits -= 1
        
        # Log question creation
        models_str = ', '.join(models)
        log_entry = LogEntry(
            project='ask_many_llms',
            category='Ask Question',
            actor_id=current_user.id,
            description=f"User asked question to {len(models)} models ({models_str}): {content[:100]}..."
        )
        db.session.add(log_entry)
        
        credit_log = LogEntry(
            project='ask_many_llms',
            category='Credit Usage',
            actor_id=current_user.id,
            description=f"Used 1 credit for question {question.id}. Remaining: {current_user.credits}"
        )
        db.session.add(credit_log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'question_id': question.id,
            'remaining_credits': current_user.credits
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/api/query-model', methods=['POST'])
@login_required
def api_query_model():
    """Query a single model for a question"""
    try:
        question_id = request.json.get('question_id')
        model_name = request.json.get('model')
        content = request.json.get('content')
        concise = request.json.get('concise', False)
        
        if not question_id or not model_name or not content:
            return jsonify({'error': 'Missing required parameters'}), 400
        
        # Verify question exists and belongs to user
        question = LLMQuestion.query.get(question_id)
        if not question or question.user_id != current_user.id:
            return jsonify({'error': 'Question not found'}), 404
        
        # Query the model
        llm_service_instance = LLMService()
        responses = llm_service_instance.get_responses(
            question=content,
            selected_models=[model_name],
            concise=concise
        )
        
        if not responses:
            return jsonify({'error': 'No response from model'}), 500
        
        response = responses[0]
        metadata = response['metadata']
        
        # Check for errors
        if 'error' in metadata:
            error_log = LogEntry(
                project='ask_many_llms',
                category='LLM Error',
                actor_id=current_user.id,
                description=f"LLM '{response['llm_name']}' ({metadata.get('model', 'N/A')}) failed for question {question_id}. Error: {metadata['error']}"
            )
            db.session.add(error_log)
            db.session.commit()
            
            return jsonify({
                'success': False,
                'model': response['llm_name'],
                'error': metadata['error']
            })
        
        # Save response
        response_record = LLMResponse(
            question_id=question_id,
            content=response['content'],
            llm_name=response['llm_name'],
            model_name=metadata.get('model', response['llm_name']),
            input_tokens=metadata['input_tokens'],
            output_tokens=metadata['output_tokens'],
            total_tokens=metadata.get('total_tokens', metadata['input_tokens'] + metadata['output_tokens']),
            input_cost=metadata.get('input_cost', 0),
            output_cost=metadata.get('output_cost', 0),
            response_time=metadata.get('response_time')
        )
        db.session.add(response_record)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'model': response['llm_name'],
            'response_time': metadata.get('response_time')
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/api/generate-summary', methods=['POST'])
@login_required
def api_generate_summary():
    """Generate a summary for a question"""
    try:
        question_id = request.json.get('question_id')
        
        if not question_id:
            return jsonify({'error': 'Missing question_id'}), 400
        
        # Verify question exists and belongs to user
        question = LLMQuestion.query.get(question_id)
        if not question or question.user_id != current_user.id:
            return jsonify({'error': 'Question not found'}), 404
        
        # Get all responses for this question
        responses = LLMResponse.query.filter_by(question_id=question_id).all()
        
        if len(responses) < 2:
            return jsonify({'success': False, 'error': 'Not enough responses to summarize'})
        
        # Generate summary
        llm_service_instance = LLMService()
        summary_dict = llm_service_instance.generate_summary(question.content, responses)
        
        if not summary_dict:
            return jsonify({'success': False, 'error': 'Failed to generate summary'})
        
        # Create LLMResponse record for the summary
        metadata = summary_dict['metadata']
        summary_record = LLMResponse(
            question_id=question_id,
            content=summary_dict['content'],
            llm_name=summary_dict['llm_name'],
            model_name=metadata.get('model', 'gemini-2.5-flash'),
            input_tokens=metadata['input_tokens'],
            output_tokens=metadata['output_tokens'],
            total_tokens=metadata.get('total_tokens', metadata['input_tokens'] + metadata['output_tokens']),
            input_cost=metadata.get('input_cost', 0),
            output_cost=metadata.get('output_cost', 0),
            response_time=metadata.get('response_time')
        )
        db.session.add(summary_record)
        db.session.flush()  # Get the ID without committing yet
        
        # Link summary to question
        question.summary_response_id = summary_record.id
        db.session.commit()
        
        return jsonify({
            'success': True,
            'response_time': summary_record.response_time
        })
        
    except Exception as e:
        db.session.rollback()
        error_log = LogEntry(
            project='ask_many_llms',
            category='LLM Error',
            actor_id=current_user.id,
            description=f"Failed to generate summary for question {question_id}. Error: {str(e)}"
        )
        db.session.add(error_log)
        db.session.commit()
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/ask', methods=['GET', 'POST'])
@login_required
def ask_question():
    """Form to ask a question to multiple LLMs"""
    form = AskManyLLMsForm()
    if form.validate_on_submit():
        if current_user.credits < 1:
            flash('You do not have enough credits to ask a question.', 'error')
            return redirect(url_for('main.index'))
        
        # Create the question
        question = LLMQuestion(
            content=form.content.data,
            user_id=current_user.id
        )
        db.session.add(question)
        db.session.commit()
        
        # Log question creation with models selected
        models_str = ', '.join(form.models.data)
        log_entry = LogEntry(
            project='ask_many_llms',
            category='Ask Question',
            actor_id=current_user.id,
            description=f"User asked question to {len(form.models.data)} models ({models_str}): {question.content[:100]}..."
        )
        db.session.add(log_entry)
        
        # Get responses from selected models
        llm_service_instance = LLMService()
        responses = llm_service_instance.get_responses(
            question=form.content.data,
            selected_models=form.models.data,
            concise=form.concise.data
        )
        
        # Create response records and log any errors
        error_count = 0
        for response in responses:
            metadata = response['metadata']
            response_record = LLMResponse(
                question_id=question.id,
                content=response['content'],
                llm_name=response['llm_name'],
                model_name=metadata.get('model', response['llm_name']),
                input_tokens=metadata['input_tokens'],
                output_tokens=metadata['output_tokens'],
                total_tokens=metadata.get('total_tokens', metadata['input_tokens'] + metadata['output_tokens']),
                input_cost=metadata.get('input_cost', 0),
                output_cost=metadata.get('output_cost', 0),
                response_time=metadata.get('response_time')
            )
            db.session.add(response_record)
            
            # Log LLM errors
            if 'error' in metadata:
                error_count += 1
                error_log = LogEntry(
                    project='ask_many_llms',
                    category='LLM Error',
                    actor_id=current_user.id,
                    description=f"LLM API error for {response['llm_name']} (question {question.id}): {metadata['error']}"
                )
                db.session.add(error_log)
        
        # Log summary if there were errors
        if error_count > 0:
            summary_log = LogEntry(
                project='ask_many_llms',
                category='Question with Errors',
                actor_id=current_user.id,
                description=f"Question {question.id} completed with {error_count}/{len(responses)} model errors"
            )
            db.session.add(summary_log)
        
        # Deduct credits and log
        current_user.credits -= 1
        credit_log = LogEntry(
            project='ask_many_llms',
            category='Credit Usage',
            actor_id=current_user.id,
            description=f"Used 1 credit for question {question.id}. Remaining: {current_user.credits}"
        )
        db.session.add(credit_log)
        db.session.commit()
        
        flash('Your question has been submitted!', 'success')
        return redirect(url_for('ask_many_llms.view_question', question_id=question.id))
    
    return render_template('ask_many_llms/ask.html', form=form)

@bp.route('/question/<int:question_id>')
@login_required
def view_question(question_id):
    """View a question and all LLM responses"""
    question = LLMQuestion.query.get_or_404(question_id)
    if question.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to view this question.', 'error')
        return redirect(url_for('main.index'))
    
    # Get responses for this question, excluding the summary response
    responses = [r for r in question.responses if r.id != question.summary_response_id]
    
    # Generate summary if we have responses but no summary yet
    if responses and not question.summary_response:
        try:
            # Format responses for summary generation
            formatted_responses = [{
                'llm_name': r.llm_name,
                'content': r.content
            } for r in responses]
            
            # Generate summary
            llm_service_instance = LLMService()
            summary = llm_service_instance.generate_summary(question.content, formatted_responses)
            
            # Create summary response record
            summary_response = LLMResponse(
                question_id=question.id,
                content=summary['content'],
                llm_name=summary['llm_name'],
                model_name=summary['metadata']['model'],
                input_tokens=summary['metadata']['input_tokens'],
                output_tokens=summary['metadata']['output_tokens'],
                total_tokens=summary['metadata']['total_tokens'],
                input_cost=summary['metadata']['input_cost'],
                output_cost=summary['metadata']['output_cost'],
                response_time=summary['metadata'].get('response_time')
            )
            
            # Save summary response and update question
            db.session.add(summary_response)
            db.session.flush()  # Get the ID of the new response
            question.summary_response_id = summary_response.id
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error generating summary: {str(e)}', 'error')
            # Log summary generation error
            error_log = LogEntry(
                project='ask_many_llms',
                category='Summary Generation Error',
                actor_id=current_user.id,
                description=f"Failed to generate summary for question {question_id}: {str(e)}"
            )
            db.session.add(error_log)
            db.session.commit()
    
    return render_template('ask_many_llms/view.html', 
                         question=question, 
                         responses=responses,
                         summary_response=question.summary_response)

@bp.route('/questions')
@login_required
def list_questions():
    """List all questions asked by the current user"""
    questions = LLMQuestion.query.options(db.joinedload(LLMQuestion.responses)).filter_by(user_id=current_user.id).order_by(LLMQuestion.timestamp.desc()).all()
    
    # Calculate total costs for each question
    for question in questions:
        question.total_cost = sum(
            (response.input_cost or 0.0) + (response.output_cost or 0.0)
            for response in question.responses
        )
    
    return render_template('ask_many_llms/list.html', questions=questions)

@bp.route('/admin/questions')
@login_required
def admin_list_questions():
    """Admin view of all questions from all users"""
    if not current_user.is_admin:
        flash('You do not have permission to access this page.', 'error')
        return redirect(url_for('main.index'))
    
    questions = LLMQuestion.query.options(db.joinedload(LLMQuestion.responses)).order_by(LLMQuestion.timestamp.desc()).all()
    
    # Calculate total costs for each question
    for question in questions:
        question.total_cost = sum(
            (response.input_cost or 0.0) + (response.output_cost or 0.0)
            for response in question.responses
        )
    
    return render_template('ask_many_llms/admin_list.html', questions=questions)

@bp.route('/admin/question/<int:question_id>/delete', methods=['POST'])
@login_required
def admin_delete_question(question_id):
    """Admin endpoint to delete a question"""
    if not current_user.is_admin:
        flash('You do not have permission to delete questions.', 'error')
        return redirect(url_for('main.index'))
    
    question = LLMQuestion.query.get_or_404(question_id)
    try:
        # Log question deletion
        log_entry = LogEntry(
            project='ask_many_llms',
            category='Delete Question',
            actor_id=current_user.id,
            description=f"Admin deleted question {question_id} from user {question.user.email}"
        )
        db.session.add(log_entry)
        
        db.session.delete(question)
        db.session.commit()
        flash('Question deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting question: {str(e)}', 'error')
    
    return redirect(url_for('ask_many_llms.admin_list_questions'))

