from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import User, LogEntry, db
from app.forms import AdminPasswordResetForm, AdminCreditForm
from functools import wraps
import pytz

admin_bp = Blueprint('admin', __name__)

# Admin decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required.')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/reset_password', methods=['GET', 'POST'])
@login_required
@admin_required
def reset_password():
    form = AdminPasswordResetForm()
    form.email.choices = [(user.email, user.email) for user in User.query.all()]

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            user.set_password(form.new_password.data)
            db.session.commit()
            flash('Password reset successfully.')

            log_entry = LogEntry(category='Reset Password', actor_id=current_user.id, description=f"{current_user.email} reset password of {user.email}")
            db.session.add(log_entry)
            db.session.commit()
        else:
            flash('User not found.')

    return render_template('admin/reset_password.html', form=form)

@admin_bp.route('/view_logs')
@login_required
@admin_required
def view_logs():
    user_tz = pytz.timezone(current_user.time_zone)

    # This is the fixed version of your query - it was using current_user_id instead of actor_id
    log_entries = LogEntry.query.join(User, LogEntry.actor_id == User.id)
    log_entries = log_entries.order_by(LogEntry.timestamp.desc()).all()

    for log in log_entries:
        localized_timestamp = log.timestamp.replace(tzinfo=pytz.utc).astimezone(user_tz)
        tz_abbr = localized_timestamp.tzname()  # Gets the time zone abbreviation
        log.formatted_timestamp = localized_timestamp.strftime('%Y-%m-%d, %I:%M:%S %p ') + tz_abbr
    
    return render_template('admin/view_logs.html', log_entries=log_entries)

@admin_bp.route('/manage_credits', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_credits():
    form = AdminCreditForm()
    users = User.query.all()
    form.email.choices = [(user.email, user.email) for user in users]

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            try:
                credits_to_add = int(form.credits.data)
                if credits_to_add <= 0:
                    flash('Please enter a positive number of credits.')
                    return render_template('admin/manage_credits.html', form=form, users=users)
                
                user.credits = (user.credits or 0) + credits_to_add
                db.session.commit()
                flash(f'Successfully added {credits_to_add} credits to {user.email}.')

                log_entry = LogEntry(
                    category='Add Credits',
                    actor_id=current_user.id,
                    description=f"{current_user.email} added {credits_to_add} credits to {user.email}"
                )
                db.session.add(log_entry)
                db.session.commit()
            except ValueError:
                flash('Please enter a valid number of credits.')
        else:
            flash('User not found.')

    return render_template('admin/manage_credits.html', form=form, users=users)