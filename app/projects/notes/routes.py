from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.utils.logging import log_project_visit

notes_bp = Blueprint('notes', __name__,
                     url_prefix='/notes',
                     template_folder='templates')


@notes_bp.route('/')
@login_required
def index():
    """Main page: list of active notes."""
    log_project_visit('notes', 'Notes')
    return render_template('notes/index.html')


@notes_bp.route('/archived')
@login_required
def archived():
    """List of archived notes."""
    return render_template('notes/archived.html')


@notes_bp.route('/new')
@login_required
def new():
    """Show form to create a new note."""
    return render_template('notes/new.html')


@notes_bp.route('/create', methods=['POST'])
@login_required
def create():
    """Create a new note and redirect to edit page."""
    # Placeholder - will be implemented in 1.5
    flash('Create functionality coming soon', 'info')
    return redirect(url_for('notes.index'))


@notes_bp.route('/<int:note_id>')
@login_required
def view(note_id):
    """View a note with rendered markdown."""
    # Placeholder - will be implemented in 1.6
    return render_template('notes/view.html', note_id=note_id)


@notes_bp.route('/<int:note_id>/edit')
@login_required
def edit(note_id):
    """Edit a note."""
    # Placeholder - will be implemented in 1.7
    return render_template('notes/edit.html', note_id=note_id)


@notes_bp.route('/<int:note_id>/save', methods=['POST'])
@login_required
def save(note_id):
    """Save changes to a note."""
    # Placeholder - will be implemented in 1.7
    flash('Save functionality coming soon', 'info')
    return redirect(url_for('notes.edit', note_id=note_id))


@notes_bp.route('/<int:note_id>/delete', methods=['POST'])
@login_required
def delete(note_id):
    """Permanently delete a note."""
    # Placeholder - will be implemented in 1.8
    flash('Delete functionality coming soon', 'info')
    return redirect(url_for('notes.index'))


@notes_bp.route('/<int:note_id>/archive', methods=['POST'])
@login_required
def archive(note_id):
    """Archive a note."""
    # Placeholder - will be implemented in 2.1
    flash('Archive functionality coming soon', 'info')
    return redirect(url_for('notes.index'))


@notes_bp.route('/<int:note_id>/unarchive', methods=['POST'])
@login_required
def unarchive(note_id):
    """Unarchive a note."""
    # Placeholder - will be implemented in 2.1
    flash('Unarchive functionality coming soon', 'info')
    return redirect(url_for('notes.index'))


@notes_bp.route('/search')
@login_required
def search():
    """Search notes."""
    # Placeholder - will be implemented in 2.4
    return render_template('notes/search.html')
