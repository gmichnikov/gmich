"""
Email service for sending emails via Mailgun API.
Copied from scripts/send_email.py - do not modify the original script.
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
    
    data = {
        "from": f"Greg <{config['sender_email']}>",
        "to": to_email,
        "subject": subject,
        "text": text_content
    }
    
    if html_content:
        data["html"] = html_content
    
    try:
        response = requests.post(
            f"https://api.mailgun.net/v3/{config['domain']}/messages",
            auth=("api", config['api_key']),
            data=data
        )
        response.raise_for_status()
        logger.info(f"Email sent successfully to {to_email}")
        return response
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending email to {to_email}: {e}")
        raise


def send_verification_email(user, token):
    """
    Send email verification email to a user.
    
    Args:
        user: User model instance
        token: Verification token string
    
    Returns:
        requests.Response object if successful, None if error (logged)
    
    Note: Must be called within a Flask application context.
    """
    # Generate verification URL using Flask's url_for
    # This requires being within a Flask application context (which we will be in routes)
    # url_for with _external=True automatically uses the request's host URL
    verification_url = url_for('auth.verify_email', token=token, _external=True)
    
    subject = "Verify Your Email Address"
    
    text_content = f"""Hello,

Thank you for registering! Please verify your email address by clicking the link below:

{verification_url}

This link will expire in 24 hours.

If you did not create an account, please ignore this email.

Best regards,
gregmichnikov.com
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
        <h2>Verify Your Email Address</h2>
        <p>Hello,</p>
        <p>Thank you for registering! Please verify your email address by clicking the button below:</p>
        <a href="{verification_url}" style="display: inline-block; padding: 12px 24px; background-color: #28a745; color: #ffffff !important; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; text-align: center;">Verify Email Address</a>
        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #666;">{verification_url}</p>
        <p>This link will expire in 24 hours.</p>
        <p>If you did not create an account, please ignore this email.</p>
        <div class="footer">
            <p>Best regards,<br>gregmichnikov.com</p>
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
        # Log the error but don't crash - registration should still succeed
        logger.error(f"Failed to send verification email to {user.email}: {e}")
        return None

