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


def send_password_reset_email(user, token):
    """
    Send password reset email to a user.
    
    Args:
        user: User model instance
        token: Password reset token string
    
    Returns:
        requests.Response object if successful, None if error (logged)
    
    Note: Must be called within a Flask application context.
    """
    # Generate password reset URL using Flask's url_for
    # This requires being within a Flask application context (which we will be in routes)
    # url_for with _external=True automatically uses the request's host URL
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    
    subject = "Reset Your Password"
    
    text_content = f"""Hello,

You requested to reset your password. Click the link below to reset it:

{reset_url}

This link will expire in 1 hour.

If you did not request a password reset, please ignore this email. Your password will remain unchanged.

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
        <h2>Reset Your Password</h2>
        <p>Hello,</p>
        <p>You requested to reset your password. Click the button below to reset it:</p>
        <a href="{reset_url}" style="display: inline-block; padding: 12px 24px; background-color: #28a745; color: #ffffff !important; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; text-align: center;">Reset Password</a>
        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #666;">{reset_url}</p>
        <p>This link will expire in 1 hour.</p>
        <p>If you did not request a password reset, please ignore this email. Your password will remain unchanged.</p>
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
        # Log the error but don't crash
        logger.error(f"Failed to send password reset email to {user.email}: {e}")
        return None


def send_password_reset_confirmation_email(user):
    """
    Send confirmation email after password has been successfully reset.
    
    Args:
        user: User model instance
    
    Returns:
        requests.Response object if successful, None if error (logged)
    
    Note: Must be called within a Flask application context.
    """
    subject = "Your Password Has Been Reset"
    
    text_content = f"""Hello,

Your password has been successfully reset.

If you did not reset your password, please contact us immediately.

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
        <h2>Your Password Has Been Reset</h2>
        <p>Hello,</p>
        <p>Your password has been successfully reset.</p>
        <p>If you did not reset your password, please contact us immediately.</p>
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
        # Log the error but don't crash
        logger.error(f"Failed to send password reset confirmation email to {user.email}: {e}")
        return None


def send_swap_request_email(recipient_user, requestor_user, swap_request, tokens_for_recipient, list_name):
    """
    Send swap request notification email to a potential swap partner.
    
    Args:
        recipient_user: User model instance (the person receiving the email)
        requestor_user: User model instance (the person who created the swap request)
        swap_request: SwapRequest model instance
        tokens_for_recipient: List of SwapToken instances for this recipient
        list_name: Name of the signup list
    
    Returns:
        requests.Response object if successful, None if error (logged)
    
    Note: Must be called within a Flask application context.
    """
    from app.projects.better_signups.models import Event, Item
    
    # Get requestor's element details
    requestor_signup = swap_request.requestor_signup
    requestor_family_member = swap_request.requestor_family_member
    
    if requestor_signup.event_id:
        requestor_element = Event.query.get(requestor_signup.event_id)
        if requestor_element.event_type == "date":
            requestor_element_desc = requestor_element.event_date.strftime('%B %d, %Y')
        else:
            requestor_element_desc = f"{requestor_element.event_datetime.strftime('%B %d, %Y at %I:%M %p')} ({requestor_element.timezone})"
    else:
        requestor_element = Item.query.get(requestor_signup.item_id)
        requestor_element_desc = requestor_element.name
    
    subject = f"Swap Request in '{list_name}'"
    
    # Build swap options text
    swap_options_text = []
    swap_options_html = []
    
    for token in tokens_for_recipient:
        # Get recipient's signup details
        recipient_signup = token.recipient_signup
        recipient_family_member = recipient_signup.family_member
        
        # Get the element recipient is currently signed up for (what they're swapping FROM)
        if recipient_signup.event_id:
            from app.projects.better_signups.models import Event
            recipient_current_element = Event.query.get(recipient_signup.event_id)
            if recipient_current_element.event_type == "date":
                recipient_from_desc = recipient_current_element.event_date.strftime('%B %d, %Y')
            else:
                recipient_from_desc = f"{recipient_current_element.event_datetime.strftime('%B %d, %Y at %I:%M %p')} ({recipient_current_element.timezone})"
        else:
            from app.projects.better_signups.models import Item
            recipient_current_element = Item.query.get(recipient_signup.item_id)
            recipient_from_desc = recipient_current_element.name
        
        # Text version
        swap_options_text.append(
            f"  • {recipient_family_member.display_name}:\n"
            f"    You swap FROM: {recipient_from_desc}\n"
            f"    You swap TO: {requestor_element_desc}\n"
            f"    Link: {swap_url}"
        )
        
        # HTML version
        swap_options_html.append(f"""
            <div style="margin: 15px 0; padding: 15px; background-color: #f5f5f5; border-radius: 5px;">
                <p style="margin: 0 0 10px 0; font-weight: bold; color: #333;">
                    {recipient_family_member.display_name}
                </p>
                <p style="margin: 0 0 5px 0; color: #666;">
                    <strong>You swap FROM:</strong> <span style="text-decoration: line-through;">{recipient_from_desc}</span>
                </p>
                <p style="margin: 0 0 10px 0; color: #666;">
                    <strong>You swap TO:</strong> <strong style="color: #28a745;">{requestor_element_desc}</strong>
                </p>
                <a href="{swap_url}" style="display: inline-block; padding: 10px 20px; background-color: #007bff; color: #ffffff !important; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    Complete This Swap
                </a>
            </div>
        """)
    
    text_content = f"""Hello {recipient_user.full_name},

{requestor_user.full_name} would like to swap signups with you in the list '{list_name}'.

They want to get rid of: {requestor_element_desc}

Your family has the following swap option(s):

{chr(10).join(swap_options_text)}

What happens if you click a link:
- Your family member will be moved to '{requestor_element_desc}'
- {requestor_family_member.display_name} will get your spot
- The swap happens instantly - first click wins!

If you're not interested, simply ignore this email.

Best regards,
gregmichnikov.com
"""
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .info-box {{ background-color: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
        .warning {{ background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Swap Request in '{list_name}'</h2>
        <p>Hello {recipient_user.full_name},</p>
        <p><strong>{requestor_user.full_name}</strong> would like to swap signups with you.</p>
        
        <div class="info-box">
            <p style="margin: 0;"><strong>They want to get rid of:</strong> {requestor_element_desc}</p>
        </div>
        
        <h3>Your Swap Option(s):</h3>
        <p>Click any button below to complete that swap:</p>
        
        {''.join(swap_options_html)}
        
        <div class="warning">
            <p style="margin: 0 0 10px 0; font-weight: bold;">⚡ Important:</p>
            <p style="margin: 0;">
                • The swap happens <strong>instantly</strong> when you click<br>
                • <strong>First click wins!</strong> If someone else clicks first, the swap will already be completed<br>
                • Both signups will be swapped automatically
            </p>
        </div>
        
        <p>If you're not interested, simply ignore this email.</p>
        
        <div class="footer">
            <p>Best regards,<br>gregmichnikov.com</p>
        </div>
    </div>
</body>
</html>
"""
    
    try:
        return send_email(
            to_email=recipient_user.email,
            subject=subject,
            text_content=text_content,
            html_content=html_content
        )
    except Exception as e:
        # Log the error but don't crash - swap request creation should still succeed
        logger.error(f"Failed to send swap request email to {recipient_user.email}: {e}")
        return None
