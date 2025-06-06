from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import Question, Response, LogEntry
from app.forms import QuestionForm
from app.services.llm_service import LLMService, PRICING

bp = Blueprint('questions', __name__)
llm_service = LLMService()

@bp.route('/ask', methods=['GET', 'POST'])
@login_required
def ask_question():
    form = QuestionForm()
    if form.validate_on_submit():
        if current_user.credits < 1:
            flash('You do not have enough credits to ask a question.', 'error')
            return redirect(url_for('main.index'))
        
        # Create the question
        question = Question(
            content=form.content.data,
            user_id=current_user.id
        )
        db.session.add(question)
        db.session.commit()
        
        # Log question creation
        log_entry = LogEntry(
            category='Ask Question',
            actor_id=current_user.id,
            description=f"User asked question: {question.content[:100]}..."
        )
        db.session.add(log_entry)
        
        # Get responses from selected models
        llm_service = LLMService()
        responses = llm_service.get_responses(
            question=form.content.data,
            selected_models=form.models.data,
            concise=form.concise.data
        )
        
        # Create response records
        for response in responses:
            metadata = response['metadata']
            response_record = Response(
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
        
        # Deduct credits
        current_user.credits -= 1
        db.session.commit()
        
        flash('Your question has been submitted!', 'success')
        return redirect(url_for('questions.view_question', question_id=question.id))
    
    return render_template('questions/ask.html', form=form)

@bp.route('/question/<int:question_id>')
@login_required
def view_question(question_id):
    question = Question.query.get_or_404(question_id)
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
            summary = llm_service.generate_summary(question.content, formatted_responses)
            
            # Create summary response record
            summary_response = Response(
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
    
    return render_template('questions/view.html', 
                         question=question, 
                         responses=responses,
                         summary_response=question.summary_response)

@bp.route('/questions')
@login_required
def list_questions():
    questions = Question.query.options(db.joinedload(Question.responses)).filter_by(user_id=current_user.id).order_by(Question.timestamp.desc()).all()
    
    # Calculate total costs for each question
    for question in questions:
        question.total_cost = sum(
            (response.input_cost or 0.0) + (response.output_cost or 0.0)
            for response in question.responses
        )
    
    return render_template('questions/list.html', questions=questions)

@bp.route('/admin/questions')
@login_required
def admin_list_questions():
    if not current_user.is_admin:
        flash('You do not have permission to access this page.', 'error')
        return redirect(url_for('main.index'))
    
    questions = Question.query.options(db.joinedload(Question.responses)).order_by(Question.timestamp.desc()).all()
    
    # Calculate total costs for each question
    for question in questions:
        question.total_cost = sum(
            (response.input_cost or 0.0) + (response.output_cost or 0.0)
            for response in question.responses
        )
    
    return render_template('questions/admin_list.html', questions=questions)

@bp.route('/admin/question/<int:question_id>/delete', methods=['POST'])
@login_required
def admin_delete_question(question_id):
    if not current_user.is_admin:
        flash('You do not have permission to delete questions.', 'error')
        return redirect(url_for('main.index'))
    
    question = Question.query.get_or_404(question_id)
    try:
        # Log question deletion
        log_entry = LogEntry(
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
    
    return redirect(url_for('questions.admin_list_questions')) 