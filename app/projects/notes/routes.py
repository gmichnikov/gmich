from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from zoneinfo import ZoneInfo

from app.utils.logging import log_project_visit
from app.projects.notes.models import Note

notes_bp = Blueprint('notes', __name__,
                     url_prefix='/notes',
                     template_folder='templates')


# --- Helper Functions ---

def get_note_or_404(note_id):
    """
    Get a note by ID, ensuring it belongs to the current user.
    Returns 404 if note doesn't exist or belongs to different user.
    """
    note = Note.query.get(note_id)
    if note is None or note.user_id != current_user.id:
        abort(404)
    return note


def format_datetime_for_user(dt, user):
    """
    Convert UTC datetime to user's timezone and format as 'Jan 23, 2026 3:45 PM'.
    """
    if dt is None:
        return ''
    user_tz = ZoneInfo(user.time_zone or 'UTC')
    local_dt = dt.replace(tzinfo=ZoneInfo('UTC')).astimezone(user_tz)
    return local_dt.strftime('%b %-d, %Y %-I:%M %p')


def content_preview(content, max_length=100):
    """
    Truncate content to max_length characters.
    Returns '(empty)' if content is empty/None.
    Adds '...' if truncated.
    """
    if not content or not content.strip():
        return '(empty)'
    if len(content) <= max_length:
        return content
    return content[:max_length] + '...'


# --- Template Filters ---

@notes_bp.app_template_filter('note_datetime')
def note_datetime_filter(dt):
    """Jinja filter to format datetime for current user's timezone."""
    return format_datetime_for_user(dt, current_user)


@notes_bp.app_template_filter('note_preview')
def note_preview_filter(content):
    """Jinja filter to create content preview."""
    return content_preview(content)


@notes_bp.route('/')
@login_required
def index():
    """Main page: list of active notes."""
    log_project_visit('notes', 'Notes')
    notes = Note.query.filter_by(
        user_id=current_user.id,
        is_archived=False
    ).order_by(Note.modified_at.desc()).all()
    return render_template('notes/index.html', notes=notes)


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
