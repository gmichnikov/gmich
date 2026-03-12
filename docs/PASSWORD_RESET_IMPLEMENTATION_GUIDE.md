# Password Reset via Email – Implementation Guide

A complete guide to replicating the password reset functionality in another project. This doc covers database schema, Mailgun setup, environment variables, rate limiting, security practices, and all code needed.

---

## Table of Contents
1. [High-Level Flow](#high-level-flow)
2. [Database Fields](#database-fields)
3. [Mailgun Setup](#mailgun-setup)
4. [Environment Variables](#environment-variables)
5. [Dependencies](#dependencies)
6. [Email Service Code](#email-service-code)
7. [User Model Methods](#user-model-methods)
8. [Forms](#forms)
9. [Auth Routes](#auth-routes)
10. [Rate Limiting](#rate-limiting)
11. [Templates](#templates)
12. [Integration Checklist](#integration-checklist)

---

## High-Level Flow

1. **Request reset**: User visits `/request-password-reset`, enters email, submits.
2. **Lookup**: User is found by email (case-insensitive). If not found, still show generic success message (prevents email enumeration).
3. **Token**: Generate secure token, store in DB with 1-hour expiry. Any existing reset token is overwritten.
4. **Email**: Send email with link `{base_url}/reset-password?token={token}`.
5. **Reset**: User clicks link, lands on `/reset-password` with token. They enter new password, submit.
6. **Validate**: Token is checked for existence, match, and expiry. If valid, password is updated, token is cleared, confirmation email sent, redirect to login.

**Security practices used:**
- Case-insensitive email lookup (handles `User@Example.com` vs `user@example.com`)
- Generic success message regardless of whether user exists (no email enumeration)
- Rate limiting (3 per hour, 5 per 30 days per email)
- Single-use tokens (cleared after successful reset)
- 1-hour token expiry
- Cryptographically secure tokens (`secrets.token_urlsafe(32)`)

---

## Database Fields

Add these columns to your User model:

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `password_reset_token` | String(100) | Yes | The token string (URL-safe, ~43 chars from `secrets.token_urlsafe(32)`) |
| `password_reset_expiry` | DateTime | Yes | UTC datetime when the token expires (1 hour from generation) |

**Migration (Alembic example):**
```python
def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('password_reset_token', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('password_reset_expiry', sa.DateTime(), nullable=True))

def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('password_reset_expiry')
        batch_op.drop_column('password_reset_token')
```

---

## Mailgun Setup

### 1. Create a Mailgun account
- Sign up at [mailgun.com](https://www.mailgun.com)

### 2. Verify your domain
- In Mailgun dashboard: **Sending** → **Domain settings**
- Add and verify your domain (add the DNS records they provide)
- For **testing only**, you can use the sandbox domain (e.g. `sandboxXXX.mailgun.org`) – but you can only send to authorized recipients in that case

### 3. Get your API key
- **Settings** → **API Keys** → copy the private API key (starts with `key-`)

### 4. Domain for API
- **Production**: Use your verified custom domain (e.g. `mail.yourdomain.com`)
- **Sandbox/testing**: Use `sandboxXXX.mailgun.org` as the domain in the API URL

The Mailgun API endpoint is: `https://api.mailgun.net/v3/{domain}/messages`  
Auth: HTTP Basic with username `api` and password = your API key.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MAILGUN_API_KEY` | Yes | Your Mailgun private API key (from dashboard) |
| `CUSTOM_DOMAIN` | Yes | The domain to send from (e.g. `mail.yourdomain.com` or `sandboxXXX.mailgun.org` for testing) |
| `SENDER_EMAIL` | Yes | The "From" address (e.g. `noreply@yourdomain.com`). Must be authorized for your domain. |

**Example `.env`:**
```
MAILGUN_API_KEY=key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CUSTOM_DOMAIN=mail.yourdomain.com
SENDER_EMAIL=noreply@yourdomain.com
```

---

## Dependencies

Add to `requirements.txt`:
```
requests
```

(You likely already have Flask, SQLAlchemy, Flask-WTF, etc. from your auth setup.)

---

## Email Service Code

Create a module (e.g. `app/utils/email_service.py` or `your_app/email_service.py`):

```python
"""
Email service for sending emails via Mailgun API.
"""
import os
import requests
import logging
from flask import url_for

logger = logging.getLogger(__name__)


def _get_mailgun_config():
    """Get Mailgun configuration from environment variables."""
    api_key = os.getenv('MAILGUN_API_KEY', '').strip()
    custom_domain = os.getenv('CUSTOM_DOMAIN', '').strip()
    sender_email = os.getenv('SENDER_EMAIL', '').strip()
    
    if not api_key:
        raise ValueError("MAILGUN_API_KEY environment variable is not set")
    if not custom_domain:
        raise ValueError("CUSTOM_DOMAIN environment variable is not set")
    if not sender_email:
        raise ValueError("SENDER_EMAIL environment variable is not set")
    
    return {
        'api_key': api_key,
        'domain': custom_domain,
        'sender_email': sender_email
    }


def send_email(to_email, subject, text_content, html_content=None):
    """
    Send an email using Mailgun API.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        text_content: Plain text email content
        html_content: Optional HTML email content
    
    Returns:
        requests.Response object if successful
    
    Raises:
        ValueError: If required environment variables are missing
        requests.exceptions.RequestException: If email sending fails
    """
    config = _get_mailgun_config()
    
    # Customize "From" display name for your app
    data = {
        "from": f"Your App Name <{config['sender_email']}>",
        "to": to_email,
        "subject": subject,
        "text": text_content
    }
    
    if html_content:
        data["html"] = html_content
    
    response = requests.post(
        f"https://api.mailgun.net/v3/{config['domain']}/messages",
        auth=("api", config['api_key']),
        data=data
    )
    response.raise_for_status()
    logger.info(f"Email sent successfully to {to_email}")
    return response


def send_password_reset_email(user, token, reset_route_name='auth.reset_password'):
    """
    Send password reset email to a user.
    
    Args:
        user: User model instance (must have .email)
        token: Password reset token string
        reset_route_name: Flask route name for reset (e.g. 'auth.reset_password')
    
    Returns:
        requests.Response if successful, None if error (logged)
    
    Note: Must be called within a Flask application context.
    """
    reset_url = url_for(reset_route_name, token=token, _external=True)
    
    subject = "Reset Your Password"
    
    text_content = f"""Hello,

You requested to reset your password. Click the link below to reset it:

{reset_url}

This link will expire in 1 hour.

If you did not request a password reset, please ignore this email. Your password will remain unchanged.

Best regards,
Your App Name
"""
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Reset Your Password</h2>
        <p>Hello,</p>
        <p>You requested to reset your password. Click the button below to reset it:</p>
        <a href="{reset_url}" style="display: inline-block; padding: 12px 24px; background-color: #28a745; color: #ffffff !important; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; text-align: center;">Reset Password</a>
        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #666;">{reset_url}</p>
        <p>This link will expire in 1 hour.</p>
        <p>If you did not request a password reset, please ignore this email. Your password will remain unchanged.</p>
        <div class="footer">
            <p>Best regards,<br>Your App Name</p>
        </div>
    </div>
</body>
</html>
"""
    
    try:
        return send_email(
            to_email=user.email,
            subject=subject,
            text_content=text_content,
            html_content=html_content
        )
    except Exception as e:
        logger.error(f"Failed to send password reset email to {user.email}: {e}")
        return None


def send_password_reset_confirmation_email(user):
    """
    Send confirmation email after password has been successfully reset.
    """
    subject = "Your Password Has Been Reset"
    
    text_content = """Hello,

Your password has been successfully reset.

If you did not reset your password, please contact us immediately.

Best regards,
Your App Name
"""
    
    html_content = """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .footer { margin-top: 30px; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Your Password Has Been Reset</h2>
        <p>Hello,</p>
        <p>Your password has been successfully reset.</p>
        <p>If you did not reset your password, please contact us immediately.</p>
        <div class="footer">
            <p>Best regards,<br>Your App Name</p>
        </div>
    </div>
</body>
</html>
"""
    
    try:
        return send_email(
            to_email=user.email,
            subject=subject,
            text_content=text_content,
            html_content=html_content
        )
    except Exception as e:
        logger.error(f"Failed to send password reset confirmation email to {user.email}: {e}")
        return None
```

---

## User Model Methods

Add these methods to your User model (or equivalent):

```python
import secrets
from datetime import datetime, timedelta

# Add columns (see Database Fields section):
# password_reset_token = db.Column(db.String(100), nullable=True)
# password_reset_expiry = db.Column(db.DateTime, nullable=True)

def generate_password_reset_token(self):
    """Generate a new password reset token, expiry 1 hour. Overwrites any existing token."""
    token = secrets.token_urlsafe(32)
    expiry = datetime.utcnow() + timedelta(hours=1)
    self.password_reset_token = token
    self.password_reset_expiry = expiry
    db.session.commit()
    return token

def is_password_reset_token_valid(self, token):
    """Check if token matches and hasn't expired."""
    if not self.password_reset_token or not self.password_reset_expiry:
        return False
    if self.password_reset_token != token:
        return False
    if datetime.utcnow() > self.password_reset_expiry:
        return False
    return True

def clear_password_reset_token(self):
    """Clear token after successful reset (single-use)."""
    self.password_reset_token = None
    self.password_reset_expiry = None
    db.session.commit()
```

Ensure you have `set_password(password)` that hashes and stores the password (e.g. via werkzeug `generate_password_hash`).

---

## Forms

Using Flask-WTF:

```python
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo

class RequestPasswordResetForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Send Reset Link")

class ResetPasswordForm(FlaskForm):
    password = PasswordField("New Password", validators=[DataRequired(), Length(min=4)])
    password_confirm = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwords must match"),
        ],
    )
    submit = SubmitField("Reset Password")
```

---

## Auth Routes

You need two routes. Adjust blueprint name and route names to match your app.

```python
from flask import render_template, redirect, url_for, request, flash
from sqlalchemy import func
from app import db  # or your db instance
from app.models import User
from app.forms import RequestPasswordResetForm, ResetPasswordForm
from app.utils.email_service import send_password_reset_email, send_password_reset_confirmation_email
from collections import defaultdict
from datetime import datetime, timedelta

# --- Rate limiting (in-memory; see Rate Limiting section) ---
_password_reset_rate_limit = defaultdict(list)
_password_reset_rate_limit_cleanup_time = datetime.utcnow()

def _check_password_reset_rate_limit(email, user_ip):
    """
    Returns (allowed, reason).
    Limits: 3 per email per hour, 5 per email per 30 days.
    """
    global _password_reset_rate_limit, _password_reset_rate_limit_cleanup_time

    if datetime.utcnow() - _password_reset_rate_limit_cleanup_time > timedelta(minutes=5):
        cutoff_30_days = datetime.utcnow() - timedelta(days=30)
        for key in list(_password_reset_rate_limit.keys()):
            _password_reset_rate_limit[key] = [
                ts for ts in _password_reset_rate_limit[key] if ts > cutoff_30_days
            ]
            if not _password_reset_rate_limit[key]:
                del _password_reset_rate_limit[key]
        _password_reset_rate_limit_cleanup_time = datetime.utcnow()

    email_key = f"email:{email}"

    cutoff_30_days = datetime.utcnow() - timedelta(days=30)
    requests_30_days = [ts for ts in _password_reset_rate_limit.get(email_key, []) if ts > cutoff_30_days]
    if len(requests_30_days) >= 5:
        return (False, "30-day limit")

    cutoff_1_hour = datetime.utcnow() - timedelta(hours=1)
    requests_1_hour = [ts for ts in _password_reset_rate_limit.get(email_key, []) if ts > cutoff_1_hour]
    if len(requests_1_hour) >= 3:
        return (False, "1-hour limit")

    if email_key not in _password_reset_rate_limit:
        _password_reset_rate_limit[email_key] = []
    _password_reset_rate_limit[email_key].append(datetime.utcnow())
    return (True, None)


@auth_bp.route("/request-password-reset", methods=["GET", "POST"])
def request_password_reset():
    form = RequestPasswordResetForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user_ip = request.remote_addr or "unknown"

        allowed, reason = _check_password_reset_rate_limit(email, user_ip)

        if not allowed:
            # Still show generic success (don't reveal rate limiting)
            flash("If that email address is registered, a password reset link has been sent.")
            return render_template("auth/request_password_reset.html", form=form)

        # Case-insensitive lookup
        user = db.session.query(User).filter(func.lower(User.email) == email).first()

        if user:
            try:
                token = user.generate_password_reset_token()
                send_password_reset_email(user, token)
            except Exception as e:
                # Log but don't crash
                pass

        # Always show success (security: no email enumeration)
        flash("If that email address is registered, a password reset link has been sent.")
        return render_template("auth/request_password_reset.html", form=form)

    return render_template("auth/request_password_reset.html", form=form)


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    token = request.args.get("token") or request.form.get("token")

    if not token:
        flash("Invalid password reset link. Please request a new one.")
        return redirect(url_for("auth.request_password_reset"))

    user = User.query.filter_by(password_reset_token=token).first()

    if not user:
        flash("Invalid or expired password reset link. Please request a new one.")
        return redirect(url_for("auth.request_password_reset"))

    if not user.is_password_reset_token_valid(token):
        flash("This password reset link has expired. Please request a new one.")
        return redirect(url_for("auth.request_password_reset"))

    form = ResetPasswordForm()

    if form.validate_on_submit():
        if not user.is_password_reset_token_valid(token):
            flash("This password reset link has expired. Please request a new one.")
            return redirect(url_for("auth.request_password_reset"))

        user.set_password(form.password.data)
        user.clear_password_reset_token()
        db.session.commit()

        try:
            send_password_reset_confirmation_email(user)
        except Exception:
            pass

        flash("Your password has been reset successfully. Please log in with your new password.")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form, token=token)
```

**Route names used:**
- `auth.request_password_reset` – request form
- `auth.reset_password` – reset form (used in `url_for` with `token=`)
- `auth.login` – post-reset redirect

---

## Rate Limiting

The implementation uses in-memory rate limiting:
- **3 requests per email per hour**
- **5 requests per email per 30 days**

When rate limited, the user still sees the generic success message (no indication they were blocked).

For production at scale, consider Redis or similar instead of `defaultdict`. The logic above is a drop-in for a small/medium app.

---

## Templates

### request_password_reset.html

```html
{% extends 'base.html' %}

{% block title %}Reset Password{% endblock %}

{% block content %}

<div class="auth-page-container">
    <div class="auth-card">
        <div class="auth-header">
            <h1 class="auth-title">Reset Password</h1>
            <p class="auth-subtitle">Enter your email to receive a reset link</p>
        </div>

        <form method="post" class="auth-form">
            {{ form.hidden_tag() }}
            
            <div class="auth-form-group">
                {{ form.email.label(class="auth-label") }}
                {{ form.email(class="auth-input", placeholder="your@email.com") }}
                {% if form.email.errors %}
                    <div class="auth-error-messages">
                        {% for error in form.email.errors %}
                            <span class="auth-error">{{ error }}</span>
                        {% endfor %}
                    </div>
                {% endif %}
            </div>

            <div class="auth-form-group">
                {{ form.submit(class="auth-submit-btn") }}
            </div>
        </form>

        <div class="auth-form-group" style="margin-top: 20px;">
            <p style="font-size: 0.9em; color: #666; text-align: center;">
                We'll send you a link to reset your password. The link will expire in 1 hour.
            </p>
        </div>

        <div class="auth-footer">
            <p class="auth-footer-text"><a href="{{ url_for('auth.login') }}" class="auth-link">Back to Login</a></p>
        </div>
    </div>
</div>

{% endblock %}
```

### reset_password.html

```html
{% extends 'base.html' %}

{% block title %}Reset Password{% endblock %}

{% block content %}

<div class="auth-page-container">
    <div class="auth-card">
        <div class="auth-header">
            <h1 class="auth-title">Reset Your Password</h1>
            <p class="auth-subtitle">Enter your new password</p>
        </div>

        <form method="post" class="auth-form">
            {{ form.hidden_tag() }}
            <input type="hidden" name="token" value="{{ token }}">
            
            <div class="auth-form-group">
                {{ form.password.label(class="auth-label") }}
                {{ form.password(class="auth-input", placeholder="Enter new password") }}
                {% if form.password.errors %}
                    <div class="auth-error-messages">
                        {% for error in form.password.errors %}
                            <span class="auth-error">{{ error }}</span>
                        {% endfor %}
                    </div>
                {% endif %}
            </div>

            <div class="auth-form-group">
                {{ form.password_confirm.label(class="auth-label") }}
                {{ form.password_confirm(class="auth-input", placeholder="Confirm new password") }}
                {% if form.password_confirm.errors %}
                    <div class="auth-error-messages">
                        {% for error in form.password_confirm.errors %}
                            <span class="auth-error">{{ error }}</span>
                        {% endfor %}
                    </div>
                {% endif %}
            </div>

            <div class="auth-form-group">
                {{ form.submit(class="auth-submit-btn") }}
            </div>
        </form>

        <div class="auth-footer">
            <p class="auth-footer-text"><a href="{{ url_for('auth.login') }}" class="auth-link">Back to Login</a></p>
        </div>
    </div>
</div>

{% endblock %}
```

**Login page link:** Add a "Forgot Password?" link:
```html
<a href="{{ url_for('auth.request_password_reset') }}" class="auth-link">Forgot Password?</a>
```

---

## Integration Checklist

- [ ] Add `password_reset_token` and `password_reset_expiry` to User model
- [ ] Run migration
- [ ] Add `generate_password_reset_token`, `is_password_reset_token_valid`, `clear_password_reset_token` to User
- [ ] Create email service module with `send_email`, `send_password_reset_email`, `send_password_reset_confirmation_email`
- [ ] Set `MAILGUN_API_KEY`, `CUSTOM_DOMAIN`, `SENDER_EMAIL` in env
- [ ] Add `RequestPasswordResetForm` and `ResetPasswordForm`
- [ ] Add `request_password_reset` and `reset_password` routes (and rate limiting)
- [ ] Create `request_password_reset.html` and `reset_password.html` templates
- [ ] Add "Forgot Password?" link on login page
- [ ] Ensure `url_for('auth.reset_password', token=token, _external=True)` produces correct base URL (check `SERVER_NAME` or proxy headers in production)

---

## Optional: Logging

The reference app logs password reset events to a `LogEntry` table (project, category, actor_id, description). You can add similar logging for audit trails; it’s not required for basic reset functionality.
