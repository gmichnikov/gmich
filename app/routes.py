from flask import render_template, redirect, url_for, flash, request
from app import app, db
from app.models import User, LogEntry
from flask_login import login_user, logout_user, login_required, current_user, LoginManager
from app.forms import RegistrationForm, LoginForm, AdminPasswordResetForm
from functools import wraps
import os
import pytz

ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required.')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Initialize the LoginManager
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route('/')
def index():
    if current_user.is_authenticated:
        email = current_user.email
        return render_template('index.html', logged_in=True, email=email)
    else:
        return render_template('index.html', logged_in=False)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            flash('Email already registered.')
            return redirect(url_for('register'))
        
        new_user = User(
            email=form.email.data,
            time_zone=form.time_zone.data,
        )
        new_user.set_password(form.password.data)
        # Automatically make user with ADMIN_EMAIL an admin
        if form.email.data == ADMIN_EMAIL:
            new_user.is_admin = True

        db.session.add(new_user)
        db.session.commit()

        log_entry = LogEntry(category='Register', actor_id=new_user.id, description=f"Email: {new_user.email}")
        db.session.add(log_entry)
        db.session.commit()

        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password')
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin/reset_password', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_reset_password():
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

@app.route('/admin/view_logs', methods=['GET', 'POST'])
@admin_required
@login_required
def admin_view_logs():
    user_tz = pytz.timezone(current_user.time_zone)

    log_entries = LogEntry.query.join(User, LogEntry.current_user_id == User.id)
    log_entries = log_entries.order_by(LogEntry.timestamp.desc()).all()

    for log in log_entries:
        localized_timestamp = log.timestamp.replace(tzinfo=pytz.utc).astimezone(user_tz)
        tz_abbr = localized_timestamp.tzname()  # Gets the time zone abbreviation
        log.formatted_timestamp = localized_timestamp.strftime('%Y-%m-%d, %I:%M:%S %p ') + tz_abbr
    return render_template('admin/view_logs.html', log_entries=log_entries)
