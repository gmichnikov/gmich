from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user
from app.models import User, LogEntry, db
from app.forms import (
    RegistrationForm,
    LoginForm,
    ResendVerificationForm,
    RequestPasswordResetForm,
    ResetPasswordForm,
)
from app.utils.email_service import (
    send_verification_email,
    send_password_reset_email,
    send_password_reset_confirmation_email,
)
from authlib.integrations.flask_client import OAuth
import os
import logging
import pytz
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

# Initialize OAuth (will be configured in create_app)
oauth = OAuth()

# Rate limiting for resend verification (in-memory, simple approach)
# Format: {identifier: [list of timestamps]}
_resend_rate_limit = defaultdict(list)
_resend_rate_limit_cleanup_time = datetime.utcnow()

# Rate limiting for password reset (in-memory, simple approach)
_password_reset_rate_limit = defaultdict(list)
_password_reset_rate_limit_cleanup_time = datetime.utcnow()


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
                ts for ts in _resend_rate_limit[key] if ts > cutoff_time
            ]
            if not _resend_rate_limit[key]:
                del _resend_rate_limit[key]
        _resend_rate_limit_cleanup_time = datetime.utcnow()

    # Check current attempts
    cutoff_time = datetime.utcnow() - timedelta(hours=window_hours)
    recent_attempts = [ts for ts in _resend_rate_limit[identifier] if ts > cutoff_time]

    if len(recent_attempts) >= max_attempts:
        return False

    # Record this attempt
    _resend_rate_limit[identifier].append(datetime.utcnow())
    return True


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    # Check if Google OAuth is configured
    from flask import current_app

    google_oauth_enabled = bool(
        current_app.config.get("GOOGLE_CLIENT_ID")
        and current_app.config.get("GOOGLE_CLIENT_SECRET")
    )

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            flash("Email already registered.")
            return redirect(url_for("auth.register"))

        new_user = User(
            email=form.email.data,
            full_name=form.full_name.data,
            short_name=form.short_name.data,
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
                project="auth",
                category="Email Verification Sent",
                actor_id=new_user.id,
                description=f"Verification email sent to {new_user.email}",
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            # Log error but don't fail registration
            logger.error(f"Failed to send verification email to {new_user.email}: {e}")
            log_entry = LogEntry(
                project="auth",
                category="Email Verification Error",
                actor_id=new_user.id,
                description=f"Failed to send verification email to {new_user.email}: {str(e)}",
            )
            db.session.add(log_entry)
            db.session.commit()

        # Log registration
        log_entry = LogEntry(
            project="auth",
            category="Register",
            actor_id=new_user.id,
            description=f"Email: {new_user.email}",
        )
        db.session.add(log_entry)
        db.session.commit()

        flash(
            "Registration successful! Please check your email to verify your account."
        )
        return redirect(url_for("auth.check_email"))
    return render_template(
        "auth/register.html", form=form, google_oauth_enabled=google_oauth_enabled
    )


@auth_bp.route("/check-email")
def check_email():
    """Display page instructing user to check their email for verification."""
    return render_template("auth/check_email.html")


@auth_bp.route("/verify-email")
def verify_email():
    """
    Verify user's email address using the token from the verification email.
    Token is passed as a query parameter.
    """
    token = request.args.get("token")

    if not token:
        flash("Invalid verification link. Please request a new verification email.")
        return render_template("auth/verify_email.html", success=False)

    # Find user by verification token
    user = User.query.filter_by(verification_token=token).first()

    if not user:
        # Log failed verification attempt (invalid token)
        log_entry = LogEntry(
            project="auth",
            category="Verification Failed",
            actor_id=None,
            description=f"Failed verification attempt with invalid token",
        )
        db.session.add(log_entry)
        db.session.commit()

        flash(
            "Invalid or expired verification link. Please request a new verification email."
        )
        return render_template("auth/verify_email.html", success=False)

    # Verify the email using the user's verify_email method
    if user.verify_email(token):
        # Log successful verification
        log_entry = LogEntry(
            project="auth",
            category="Email Verified",
            actor_id=user.id,
            description=f"Email verified for {user.email}",
        )
        db.session.add(log_entry)
        db.session.commit()

        flash("Email verified successfully! You can now log in.")
        return render_template("auth/verify_email.html", success=True)
    else:
        # Token expired or invalid
        log_entry = LogEntry(
            project="auth",
            category="Verification Failed",
            actor_id=user.id,
            description=f"Failed verification attempt for {user.email} - token expired or invalid",
        )
        db.session.add(log_entry)
        db.session.commit()

        flash(
            "This verification link has expired. Please request a new verification email."
        )
        return render_template("auth/verify_email.html", success=False)


@auth_bp.route("/resend-verification", methods=["GET", "POST"])
def resend_verification():
    """
    Allow users to request a new verification email.
    Includes rate limiting to prevent abuse.
    """
    form = ResendVerificationForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user_ip = request.remote_addr or "unknown"

        # Rate limiting: check both email and IP
        email_allowed = _check_rate_limit(
            f"email:{email}", max_attempts=3, window_hours=1
        )
        ip_allowed = _check_rate_limit(f"ip:{user_ip}", max_attempts=5, window_hours=1)

        if not email_allowed:
            logger.warning(f"Rate limit exceeded for email: {email}")
            # Still show success message (don't reveal rate limiting)
            flash(
                "If that email address is registered and not yet verified, a verification email has been sent."
            )
            return render_template("auth/resend_verification.html", form=form)

        if not ip_allowed:
            logger.warning(f"Rate limit exceeded for IP: {user_ip}")
            # Still show success message (don't reveal rate limiting)
            flash(
                "If that email address is registered and not yet verified, a verification email has been sent."
            )
            return render_template("auth/resend_verification.html", form=form)

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
                    project="auth",
                    category="Resend Verification",
                    actor_id=user.id,
                    description=f"Resend verification email requested for {user.email}",
                )
                db.session.add(log_entry)
                db.session.commit()
            except Exception as e:
                logger.error(
                    f"Failed to resend verification email to {user.email}: {e}"
                )
                log_entry = LogEntry(
                    project="auth",
                    category="Resend Verification Error",
                    actor_id=user.id,
                    description=f"Failed to resend verification email to {user.email}: {str(e)}",
                )
                db.session.add(log_entry)
                db.session.commit()
        elif user and user.email_verified:
            # User is already verified - don't reveal this, just show generic message
            logger.info(
                f"Resend verification requested for already verified email: {email}"
            )
        else:
            # User doesn't exist - don't reveal this, just show generic message
            logger.info(
                f"Resend verification requested for non-existent email: {email}"
            )

        # Always show success message (security best practice)
        flash(
            "If that email address is registered and not yet verified, a verification email has been sent."
        )
        return render_template("auth/resend_verification.html", form=form)

    return render_template("auth/resend_verification.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    # Check if Google OAuth is configured
    from flask import current_app

    google_oauth_enabled = bool(
        current_app.config.get("GOOGLE_CLIENT_ID")
        and current_app.config.get("GOOGLE_CLIENT_SECRET")
    )

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            # Check if email is verified
            if not user.email_verified:
                # Log attempted login with unverified email
                log_entry = LogEntry(
                    project="auth",
                    category="Login Attempt - Unverified Email",
                    actor_id=user.id,
                    description=f"Login attempt with unverified email: {user.email}",
                )
                db.session.add(log_entry)
                db.session.commit()

                flash(
                    "Please verify your email address before logging in. Check your email for the verification link, or request a new one below."
                )
                return render_template(
                    "auth/login.html",
                    form=form,
                    show_resend=True,
                    google_oauth_enabled=google_oauth_enabled,
                )

            # Email is verified, proceed with login
            login_user(user)

            # Log successful login
            log_entry = LogEntry(
                project="auth",
                category="Login",
                actor_id=user.id,
                description=f"Successful login for {user.email}",
            )
            db.session.add(log_entry)
            db.session.commit()

            next_page = request.args.get("next")
            return redirect(next_page or url_for("main.index"))
        else:
            # Log failed login attempt
            log_entry = LogEntry(
                project="auth",
                category="Failed Login",
                actor_id=None,
                description=f"Failed login attempt for email: {form.email.data}",
            )
            db.session.add(log_entry)
            db.session.commit()

            flash("Invalid email or password")
    return render_template(
        "auth/login.html", form=form, google_oauth_enabled=google_oauth_enabled
    )


@auth_bp.route("/logout")
def logout():
    if current_user.is_authenticated:
        # Log logout
        log_entry = LogEntry(
            project="auth",
            category="Logout",
            actor_id=current_user.id,
            description=f"User {current_user.email} logged out",
        )
        db.session.add(log_entry)
        db.session.commit()

    logout_user()
    return redirect(url_for("main.index"))


def _check_password_reset_rate_limit(email, user_ip):
    """
    Check password reset rate limits:
    - Max 3 requests per email per hour
    - Max 5 requests per email per 30 days

    Args:
        email: User email address
        user_ip: User IP address

    Returns:
        tuple: (allowed, reason) - (True, None) if allowed, (False, reason) if blocked
    """
    global _password_reset_rate_limit, _password_reset_rate_limit_cleanup_time

    # Cleanup old entries periodically (every 5 minutes)
    if datetime.utcnow() - _password_reset_rate_limit_cleanup_time > timedelta(
        minutes=5
    ):
        cutoff_30_days = datetime.utcnow() - timedelta(days=30)
        for key in list(_password_reset_rate_limit.keys()):
            _password_reset_rate_limit[key] = [
                ts for ts in _password_reset_rate_limit[key] if ts > cutoff_30_days
            ]
            if not _password_reset_rate_limit[key]:
                del _password_reset_rate_limit[key]
        _password_reset_rate_limit_cleanup_time = datetime.utcnow()

    email_key = f"email:{email}"

    # Check 30-day limit (5 requests)
    cutoff_30_days = datetime.utcnow() - timedelta(days=30)
    requests_30_days = [
        ts for ts in _password_reset_rate_limit[email_key] if ts > cutoff_30_days
    ]

    if len(requests_30_days) >= 5:
        return (False, "30-day limit")

    # Check 1-hour limit (3 requests)
    cutoff_1_hour = datetime.utcnow() - timedelta(hours=1)
    requests_1_hour = [
        ts for ts in _password_reset_rate_limit[email_key] if ts > cutoff_1_hour
    ]

    if len(requests_1_hour) >= 3:
        return (False, "1-hour limit")

    # Record this attempt
    _password_reset_rate_limit[email_key].append(datetime.utcnow())
    return (True, None)


@auth_bp.route("/request-password-reset", methods=["GET", "POST"])
def request_password_reset():
    """
    Allow users to request a password reset email.
    Includes rate limiting to prevent abuse.
    """
    form = RequestPasswordResetForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user_ip = request.remote_addr or "unknown"

        # Check rate limits
        allowed, reason = _check_password_reset_rate_limit(email, user_ip)

        if not allowed:
            logger.warning(
                f"Password reset rate limit exceeded for email: {email} ({reason})"
            )
            # Still show success message (don't reveal rate limiting)
            flash(
                "If that email address is registered, a password reset link has been sent."
            )
            return render_template("auth/request_password_reset.html", form=form)

        # Find user by email
        user = User.query.filter_by(email=email).first()

        # Security: Always show success message, even if user doesn't exist
        # This prevents email enumeration attacks
        if user:
            try:
                # Generate new token (this invalidates any existing token)
                token = user.generate_password_reset_token()
                send_password_reset_email(user, token)

                # Log password reset request
                log_entry = LogEntry(
                    project="auth",
                    category="Password Reset Requested",
                    actor_id=user.id,
                    description=f"Password reset requested for {user.email}",
                )
                db.session.add(log_entry)
                db.session.commit()
            except Exception as e:
                logger.error(
                    f"Failed to send password reset email to {user.email}: {e}"
                )
                log_entry = LogEntry(
                    project="auth",
                    category="Password Reset Error",
                    actor_id=user.id,
                    description=f"Failed to send password reset email to {user.email}: {str(e)}",
                )
                db.session.add(log_entry)
                db.session.commit()
        else:
            # User doesn't exist - don't reveal this, just show generic message
            logger.info(f"Password reset requested for non-existent email: {email}")
            # Log to database for security monitoring (no actor_id since user doesn't exist)
            log_entry = LogEntry(
                project="auth",
                category="Password Reset Requested - Non-existent Email",
                actor_id=None,
                description=f"Password reset requested for non-existent email: {email}",
            )
            db.session.add(log_entry)
            db.session.commit()

        # Always show success message (security best practice)
        flash(
            "If that email address is registered, a password reset link has been sent."
        )
        return render_template("auth/request_password_reset.html", form=form)

    return render_template("auth/request_password_reset.html", form=form)


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    """
    Reset password using token from email.
    Token is passed as a query parameter on GET, or in form data on POST.
    """
    # Get token from query parameter (GET) or form data (POST)
    token = request.args.get("token") or request.form.get("token")

    if not token:
        flash("Invalid password reset link. Please request a new one.")
        return redirect(url_for("auth.request_password_reset"))

    # Find user by password reset token
    user = User.query.filter_by(password_reset_token=token).first()

    if not user:
        # Log failed reset attempt (invalid token)
        log_entry = LogEntry(
            project="auth",
            category="Password Reset Failed",
            actor_id=None,
            description=f"Failed password reset attempt with invalid token",
        )
        db.session.add(log_entry)
        db.session.commit()

        flash("Invalid or expired password reset link. Please request a new one.")
        return redirect(url_for("auth.request_password_reset"))

    # Validate token
    if not user.is_password_reset_token_valid(token):
        # Token expired or invalid
        log_entry = LogEntry(
            project="auth",
            category="Password Reset Failed",
            actor_id=user.id,
            description=f"Failed password reset attempt for {user.email} - token expired or invalid",
        )
        db.session.add(log_entry)
        db.session.commit()

        flash("This password reset link has expired. Please request a new one.")
        return redirect(url_for("auth.request_password_reset"))

    # Token is valid, show reset form
    form = ResetPasswordForm()

    if form.validate_on_submit():
        # Double-check token is still valid (in case it expired between page load and submit)
        if not user.is_password_reset_token_valid(token):
            flash("This password reset link has expired. Please request a new one.")
            return redirect(url_for("auth.request_password_reset"))

        # Reset the password
        user.set_password(form.password.data)
        user.clear_password_reset_token()  # Clear token (single-use)
        db.session.commit()

        # Send confirmation email
        try:
            send_password_reset_confirmation_email(user)
        except Exception as e:
            logger.error(
                f"Failed to send password reset confirmation email to {user.email}: {e}"
            )

        # Log successful password reset
        log_entry = LogEntry(
            project="auth",
            category="Password Reset",
            actor_id=user.id,
            description=f"Password reset successful for {user.email}",
        )
        db.session.add(log_entry)
        db.session.commit()

        flash(
            "Your password has been reset successfully. Please log in with your new password."
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form, token=token)


@auth_bp.route("/login/google")
def login_google():
    """Initiate Google OAuth login flow."""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    # Check if Google OAuth is configured
    from flask import current_app

    if not current_app.config.get("GOOGLE_CLIENT_ID") or not current_app.config.get(
        "GOOGLE_CLIENT_SECRET"
    ):
        flash("Google login is not configured. Please contact support.")
        return redirect(url_for("auth.login"))

    # Get time zone from query parameter if provided (set by JavaScript)
    time_zone = request.args.get("timezone", "UTC")
    # Validate time zone is in pytz common timezones
    if time_zone not in pytz.common_timezones:
        time_zone = "UTC"
    session["oauth_timezone"] = time_zone

    # Get the OAuth client
    google = oauth.google

    # Redirect to Google OAuth
    redirect_uri = url_for("auth.google_callback", _external=True)
    logger.info(f"Google OAuth redirect URI: {redirect_uri}")
    return google.authorize_redirect(redirect_uri)


@auth_bp.route("/login/google/callback")
def google_callback():
    """Handle Google OAuth callback."""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    try:
        # Get the OAuth client
        google = oauth.google

        # Get the authorization token
        token = google.authorize_access_token()

        # Get user info from Google
        resp = google.get("https://www.googleapis.com/oauth2/v2/userinfo", token=token)
        resp.raise_for_status()
        user_info = resp.json()

        google_id = user_info.get("id")
        google_email = user_info.get("email", "").lower().strip()
        google_name = user_info.get("name", "")
        verified_email = user_info.get("verified_email", False)

        if not google_id or not google_email:
            logger.error("Google OAuth callback missing required fields")
            flash("Failed to retrieve information from Google. Please try again.")
            return redirect(url_for("auth.login"))

        # Check if a user with this Google ID already exists
        user = User.query.filter_by(google_id=google_id).first()

        if user:
            # User already exists with this Google account - log them in
            login_user(user)

            # Log successful login
            log_entry = LogEntry(
                project="auth",
                category="Login - Google",
                actor_id=user.id,
                description=f"Successful Google login for {user.email}",
            )
            db.session.add(log_entry)
            db.session.commit()

            next_page = request.args.get("next") or session.pop("next", None)
            return redirect(next_page or url_for("main.index"))

        # Check if a user with this email already exists (but different login method)
        existing_user = User.query.filter_by(email=google_email).first()

        if existing_user:
            # User exists with email/password - link the Google account
            # This allows them to use either login method going forward
            existing_user.google_id = google_id
            existing_user.google_email = google_email

            # Mark email as verified if Google verified it
            if verified_email:
                existing_user.email_verified = True

            db.session.commit()

            # Log the account linking
            log_entry = LogEntry(
                project="auth",
                category="Account Linked - Google",
                actor_id=existing_user.id,
                description=f"Google account linked to existing email/password account for {existing_user.email}",
            )
            db.session.add(log_entry)
            db.session.commit()

            # Log them in
            login_user(existing_user)

            # Log successful login
            log_entry = LogEntry(
                project="auth",
                category="Login - Google",
                actor_id=existing_user.id,
                description=f"Successful Google login for {existing_user.email} (account linked)",
            )
            db.session.add(log_entry)
            db.session.commit()

            flash(
                "Your Google account has been linked to your existing account. You can now use either login method."
            )
            next_page = request.args.get("next") or session.pop("next", None)
            return redirect(next_page or url_for("main.index"))

        # New user - create account
        # Use Google name if available, otherwise use placeholder
        # For short_name, try to extract first name from full name, or use full name
        google_full_name = google_name.strip() if google_name else "placeholder"
        google_short_name = (
            google_full_name.split()[0]
            if google_full_name and google_full_name != "placeholder"
            else "placeholder"
        )

        # Get time zone from session (set before OAuth redirect) or default to UTC
        time_zone = session.pop("oauth_timezone", "UTC")
        # Validate time zone is in pytz common timezones
        if time_zone not in pytz.common_timezones:
            time_zone = "UTC"

        new_user = User(
            email=google_email,
            full_name=google_full_name,
            short_name=google_short_name,
            google_id=google_id,
            google_email=google_email,
            email_verified=verified_email,  # Google verifies emails
            time_zone=time_zone,
        )

        # Automatically make user with ADMIN_EMAIL an admin
        if google_email == ADMIN_EMAIL:
            new_user.is_admin = True

        db.session.add(new_user)
        db.session.commit()

        # Log registration
        log_entry = LogEntry(
            project="auth",
            category="Register - Google",
            actor_id=new_user.id,
            description=f"New user registered via Google: {new_user.email}",
        )
        db.session.add(log_entry)
        db.session.commit()

        # Log them in
        login_user(new_user)

        # Log successful login
        log_entry = LogEntry(
            project="auth",
            category="Login - Google",
            actor_id=new_user.id,
            description=f"Successful Google login for {new_user.email}",
        )
        db.session.add(log_entry)
        db.session.commit()

        flash("Successfully logged in with Google!")
        next_page = request.args.get("next") or session.pop("next", None)
        return redirect(next_page or url_for("main.index"))

    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}", exc_info=True)
        flash("An error occurred during Google login. Please try again.")
        return redirect(url_for("auth.login"))
