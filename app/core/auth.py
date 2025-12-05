from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from app.models import User, LogEntry, db
from app.forms import RegistrationForm, LoginForm, ResendVerificationForm
from app.utils.email_service import send_verification_email
import os
import logging
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')

# Rate limiting for resend verification (in-memory, simple approach)
# Format: {identifier: [list of timestamps]}
_resend_rate_limit = defaultdict(list)
_resend_rate_limit_cleanup_time = datetime.utcnow()

def _check_rate_limit(identifier, max_attempts=3, window_hours=1):
    """
    Check if identifier has exceeded rate limit.
    
    Args:
        identifier: Email or IP address
        max_attempts: Maximum attempts allowed in time window
        window_hours: Time window in hours
    
    Returns:
        bool: True if within limit, False if exceeded
    """
    global _resend_rate_limit, _resend_rate_limit_cleanup_time
    
    # Cleanup old entries periodically (every 5 minutes)
    if datetime.utcnow() - _resend_rate_limit_cleanup_time > timedelta(minutes=5):
        cutoff_time = datetime.utcnow() - timedelta(hours=window_hours)
        for key in list(_resend_rate_limit.keys()):
            _resend_rate_limit[key] = [
                ts for ts in _resend_rate_limit[key] 
                if ts > cutoff_time
            ]
            if not _resend_rate_limit[key]:
                del _resend_rate_limit[key]
        _resend_rate_limit_cleanup_time = datetime.utcnow()
    
    # Check current attempts
    cutoff_time = datetime.utcnow() - timedelta(hours=window_hours)
    recent_attempts = [
        ts for ts in _resend_rate_limit[identifier]
        if ts > cutoff_time
    ]
    
    if len(recent_attempts) >= max_attempts:
        return False
    
    # Record this attempt
    _resend_rate_limit[identifier].append(datetime.utcnow())
    return True

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            flash('Email already registered.')
            return redirect(url_for('auth.register'))
        
        new_user = User(
            email=form.email.data,
            time_zone=form.time_zone.data,
            email_verified=False,  # New users start unverified
        )
        new_user.set_password(form.password.data)
        # Automatically make user with ADMIN_EMAIL an admin
        if form.email.data == ADMIN_EMAIL:
            new_user.is_admin = True

        db.session.add(new_user)
        db.session.commit()

        # Generate verification token and send email
        try:
            token = new_user.generate_verification_token()
            send_verification_email(new_user, token)
            
            # Log email sent
            log_entry = LogEntry(
                project='auth', 
                category='Email Verification Sent', 
                actor_id=new_user.id, 
                description=f"Verification email sent to {new_user.email}"
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            # Log error but don't fail registration
            logger.error(f"Failed to send verification email to {new_user.email}: {e}")
            log_entry = LogEntry(
                project='auth', 
                category='Email Verification Error', 
                actor_id=new_user.id, 
                description=f"Failed to send verification email to {new_user.email}: {str(e)}"
            )
            db.session.add(log_entry)
            db.session.commit()

        # Log registration
        log_entry = LogEntry(project='auth', category='Register', actor_id=new_user.id, description=f"Email: {new_user.email}")
        db.session.add(log_entry)
        db.session.commit()

        flash('Registration successful! Please check your email to verify your account.')
        return redirect(url_for('auth.check_email'))
    return render_template('auth/register.html', form=form)

@auth_bp.route('/check-email')
def check_email():
    """Display page instructing user to check their email for verification."""
    return render_template('auth/check_email.html')

@auth_bp.route('/verify-email')
def verify_email():
    """
    Verify user's email address using the token from the verification email.
    Token is passed as a query parameter.
    """
    token = request.args.get('token')
    
    if not token:
        flash('Invalid verification link. Please request a new verification email.')
        return render_template('auth/verify_email.html', success=False)
    
    # Find user by verification token
    user = User.query.filter_by(verification_token=token).first()
    
    if not user:
        # Log failed verification attempt (invalid token)
        log_entry = LogEntry(
            project='auth',
            category='Verification Failed',
            actor_id=None,
            description=f"Failed verification attempt with invalid token"
        )
        db.session.add(log_entry)
        db.session.commit()
        
        flash('Invalid or expired verification link. Please request a new verification email.')
        return render_template('auth/verify_email.html', success=False)
    
    # Verify the email using the user's verify_email method
    if user.verify_email(token):
        # Log successful verification
        log_entry = LogEntry(
            project='auth',
            category='Email Verified',
            actor_id=user.id,
            description=f"Email verified for {user.email}"
        )
        db.session.add(log_entry)
        db.session.commit()
        
        flash('Email verified successfully! You can now log in.')
        return render_template('auth/verify_email.html', success=True)
    else:
        # Token expired or invalid
        log_entry = LogEntry(
            project='auth',
            category='Verification Failed',
            actor_id=user.id,
            description=f"Failed verification attempt for {user.email} - token expired or invalid"
        )
        db.session.add(log_entry)
        db.session.commit()
        
        flash('This verification link has expired. Please request a new verification email.')
        return render_template('auth/verify_email.html', success=False)

@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    """
    Allow users to request a new verification email.
    Includes rate limiting to prevent abuse.
    """
    form = ResendVerificationForm()
    
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user_ip = request.remote_addr or 'unknown'
        
        # Rate limiting: check both email and IP
        email_allowed = _check_rate_limit(f"email:{email}", max_attempts=3, window_hours=1)
        ip_allowed = _check_rate_limit(f"ip:{user_ip}", max_attempts=5, window_hours=1)
        
        if not email_allowed:
            logger.warning(f"Rate limit exceeded for email: {email}")
            # Still show success message (don't reveal rate limiting)
            flash('If that email address is registered and not yet verified, a verification email has been sent.')
            return render_template('auth/resend_verification.html', form=form)
        
        if not ip_allowed:
            logger.warning(f"Rate limit exceeded for IP: {user_ip}")
            # Still show success message (don't reveal rate limiting)
            flash('If that email address is registered and not yet verified, a verification email has been sent.')
            return render_template('auth/resend_verification.html', form=form)
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        
        # Security: Always show success message, even if user doesn't exist
        # This prevents email enumeration attacks
        if user and not user.email_verified:
            try:
                # Generate new token and send email
                token = user.generate_verification_token()
                send_verification_email(user, token)
                
                # Log resend request
                log_entry = LogEntry(
                    project='auth',
                    category='Resend Verification',
                    actor_id=user.id,
                    description=f"Resend verification email requested for {user.email}"
                )
                db.session.add(log_entry)
                db.session.commit()
            except Exception as e:
                logger.error(f"Failed to resend verification email to {user.email}: {e}")
                log_entry = LogEntry(
                    project='auth',
                    category='Resend Verification Error',
                    actor_id=user.id,
                    description=f"Failed to resend verification email to {user.email}: {str(e)}"
                )
                db.session.add(log_entry)
                db.session.commit()
        elif user and user.email_verified:
            # User is already verified - don't reveal this, just show generic message
            logger.info(f"Resend verification requested for already verified email: {email}")
        else:
            # User doesn't exist - don't reveal this, just show generic message
            logger.info(f"Resend verification requested for non-existent email: {email}")
        
        # Always show success message (security best practice)
        flash('If that email address is registered and not yet verified, a verification email has been sent.')
        return render_template('auth/resend_verification.html', form=form)
    
    return render_template('auth/resend_verification.html', form=form)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            # Check if email is verified
            if not user.email_verified:
                # Log attempted login with unverified email
                log_entry = LogEntry(
                    project='auth', 
                    category='Login Attempt - Unverified Email', 
                    actor_id=user.id, 
                    description=f"Login attempt with unverified email: {user.email}"
                )
                db.session.add(log_entry)
                db.session.commit()
                
                flash('Please verify your email address before logging in. Check your email for the verification link, or request a new one below.')
                return render_template('auth/login.html', form=form, show_resend=True)
            
            # Email is verified, proceed with login
            login_user(user)
            
            # Log successful login
            log_entry = LogEntry(project='auth', category='Login', actor_id=user.id, description=f"Successful login for {user.email}")
            db.session.add(log_entry)
            db.session.commit()
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        else:
            # Log failed login attempt
            log_entry = LogEntry(project='auth', category='Failed Login', actor_id=None, description=f"Failed login attempt for email: {form.email.data}")
            db.session.add(log_entry)
            db.session.commit()
            
            flash('Invalid email or password')
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
def logout():
    if current_user.is_authenticated:
        # Log logout
        log_entry = LogEntry(project='auth', category='Logout', actor_id=current_user.id, description=f"User {current_user.email} logged out")
        db.session.add(log_entry)
        db.session.commit()
    
    logout_user()
    return redirect(url_for('main.index'))