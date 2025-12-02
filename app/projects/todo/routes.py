from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.projects.todo.models import TodoItem
from app.projects.todo.forms import TodoForm
from app.models import LogEntry

todo_bp = Blueprint('todo', __name__, 
                    template_folder='templates',
                    static_folder='static')

@todo_bp.route('/')
@login_required
def index():
    """Display the todo list for the current user"""
    form = TodoForm()
    
    # Get filter parameter
    filter_type = request.args.get('filter', 'all')
    
    # Query todos for current user
    query = TodoItem.query.filter_by(user_id=current_user.id)
    
    if filter_type == 'active':
        query = query.filter_by(completed=False)
    elif filter_type == 'completed':
        query = query.filter_by(completed=True)
    
    todos = query.order_by(TodoItem.created_at.desc()).all()
    
    # Count stats
    total_count = TodoItem.query.filter_by(user_id=current_user.id).count()
    active_count = TodoItem.query.filter_by(user_id=current_user.id, completed=False).count()
    completed_count = TodoItem.query.filter_by(user_id=current_user.id, completed=True).count()
    
    return render_template('todo/index.html', 
                         form=form, 
                         todos=todos,
                         filter_type=filter_type,
                         total_count=total_count,
                         active_count=active_count,
                         completed_count=completed_count)

@todo_bp.route('/add', methods=['POST'])
@login_required
def add():
    """Add a new todo item"""
    form = TodoForm()
    
    if form.validate_on_submit():
        todo = TodoItem(
            user_id=current_user.id,
            title=form.title.data
        )
        db.session.add(todo)
        db.session.commit()
        
        # Log the action
        log_entry = LogEntry(
            project='todo',
            category='Add',
            actor_id=current_user.id,
            description=f"{current_user.email} added todo: '{todo.title}'"
        )
        db.session.add(log_entry)
        db.session.commit()
        
        flash('Task added successfully!', 'success')
    else:
        for error in form.title.errors:
            flash(error, 'error')
    
    return redirect(url_for('todo.index'))

@todo_bp.route('/complete/<int:id>', methods=['POST'])
@login_required
def complete(id):
    """Toggle task completion status"""
    todo = TodoItem.query.get_or_404(id)
    
    # Ensure user owns this todo
    if todo.user_id != current_user.id:
        flash('Unauthorized action', 'error')
        return redirect(url_for('todo.index'))
    
    todo.completed = not todo.completed
    db.session.commit()
    
    status = 'completed' if todo.completed else 'reactivated'
    
    # Log the action
    log_category = 'Complete' if todo.completed else 'Reactivate'
    log_entry = LogEntry(
        project='todo',
        category=log_category,
        actor_id=current_user.id,
        description=f"{current_user.email} {status} todo: '{todo.title}'"
    )
    db.session.add(log_entry)
    db.session.commit()
    
    flash(f'Task {status}!', 'success')
    
    return redirect(url_for('todo.index', filter=request.args.get('filter', 'all')))

@todo_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    """Delete a todo item"""
    todo = TodoItem.query.get_or_404(id)
    
    # Ensure user owns this todo
    if todo.user_id != current_user.id:
        flash('Unauthorized action', 'error')
        return redirect(url_for('todo.index'))
    
    # Store title before deleting for the log
    todo_title = todo.title
    
    db.session.delete(todo)
    db.session.commit()
    
    # Log the action
    log_entry = LogEntry(
        project='todo',
        category='Delete',
        actor_id=current_user.id,
        description=f"{current_user.email} deleted todo: '{todo_title}'"
    )
    db.session.add(log_entry)
    db.session.commit()
    
    flash('Task deleted!', 'success')
    
    return redirect(url_for('todo.index', filter=request.args.get('filter', 'all')))

