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
        
        # Generate swap link for this token
        swap_url = url_for('better_signups.execute_swap', token=token.token, _external=True)
        
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


def send_waitlist_spot_offered_email(user, family_member, element, list_obj, deadline):
    """
    Send email notification when a spot is offered from the waitlist.
    
    Args:
        user: User model instance (the person receiving the email)
        family_member: FamilyMember model instance (who the spot is for)
        element: Event or Item model instance (the element with the available spot)
        list_obj: SignupList model instance (the list this is for)
        deadline: datetime object (when the offer expires, typically created_at + 24 hours)
    
    Returns:
        requests.Response object if successful, None if error (logged)
    
    Note: Must be called within a Flask application context.
    """
    from app.projects.better_signups.models import Event
    
    # Determine element description
    if isinstance(element, Event):
        if element.event_type == "date":
            element_desc = element.event_date.strftime('%B %d, %Y')
            element_type_str = "event"
        else:
            element_desc = f"{element.event_datetime.strftime('%B %d, %Y at %I:%M %p')}"
            if element.timezone:
                element_desc += f" ({element.timezone})"
            element_type_str = "event"
        
        # Add location if available
        if element.location:
            element_desc += f" - {element.location}"
    else:
        # It's an Item
        element_desc = element.name
        element_type_str = "item"
        if element.description:
            element_desc += f" - {element.description}"
    
    # Generate list URL
    list_url = url_for('better_signups.view_list', uuid=list_obj.uuid, _external=True)
    
    # Format deadline
    deadline_str = deadline.strftime('%B %d, %Y at %I:%M %p UTC')
    
    subject = f"A Spot is Available! {list_obj.name}"
    
    text_content = f"""Hello {user.full_name},

Great news! You've been offered a spot from the waitlist!

List: {list_obj.name}
{element_type_str.capitalize()}: {element_desc}
For: {family_member.display_name}

⏰ You have until {deadline_str} to confirm your spot (24 hours).

To confirm your spot:
1. Click the link below to view the list
2. Log in if needed
3. Find the {element_type_str} in the list
4. Click the "Confirm Your Spot" button

{list_url}

Important:
- You must confirm within 24 hours or the spot will be offered to the next person
- The spot will show as "Pending confirmation" until you confirm it
- Once confirmed, it's yours!

If you no longer want this spot, you can click "Decline" on the list page to pass it to the next person.

Best regards,
gregmichnikov.com
"""
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .highlight-box {{ background-color: #d4edda; padding: 20px; border-radius: 8px; margin: 20px 0; border: 2px solid #28a745; }}
        .info-box {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .warning-box {{ background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
        .btn {{ display: inline-block; padding: 15px 30px; background-color: #28a745; color: #ffffff !important; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px; margin: 20px 0; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <h2 style="color: #28a745;">🎉 A Spot is Available!</h2>
        <p>Hello {user.full_name},</p>
        <p><strong>Great news!</strong> You've been offered a spot from the waitlist!</p>
        
        <div class="highlight-box">
            <p style="margin: 0 0 10px 0;"><strong>List:</strong> {list_obj.name}</p>
            <p style="margin: 0 0 10px 0;"><strong>{element_type_str.capitalize()}:</strong> {element_desc}</p>
            <p style="margin: 0;"><strong>For:</strong> {family_member.display_name}</p>
        </div>
        
        <div class="warning-box">
            <p style="margin: 0 0 10px 0; font-weight: bold;">⏰ You have until {deadline_str} to confirm</p>
            <p style="margin: 0;">That's <strong>24 hours</strong> from now!</p>
        </div>
        
        <h3>How to Confirm Your Spot:</h3>
        <ol>
            <li>Click the button below to view the list</li>
            <li>Log in if needed</li>
            <li>Find the {element_type_str} in the list (it will have a "Pending confirmation" label)</li>
            <li>Click the green "Confirm Your Spot" button</li>
        </ol>
        
        <div style="text-align: center;">
            <a href="{list_url}" class="btn">View List and Confirm Spot</a>
        </div>
        
        <div class="info-box">
            <p style="margin: 0 0 10px 0; font-weight: bold;">Important Information:</p>
            <ul style="margin: 0; padding-left: 20px;">
                <li>You must confirm within 24 hours or the spot will go to the next person</li>
                <li>The spot shows as "Pending confirmation" until you confirm it</li>
                <li>Once confirmed, the spot is yours!</li>
                <li>Don't want it? Click "Decline" to pass it to the next person</li>
            </ul>
        </div>
        
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
        # Log the error but don't crash - cascade should still succeed
        logger.error(f"Failed to send waitlist spot offered email to {user.email}: {e}")
        return None


def send_lottery_completion_email_participant(user, list_obj, wins, waitlist_positions, losses):
    """
    Send lottery completion email to a participant.

    Args:
        user: User model instance (the person receiving the email)
        list_obj: SignupList model instance (the lottery list)
        wins: List of dicts with keys: 'element', 'family_member', 'deadline'
        waitlist_positions: List of dicts with keys: 'element', 'family_member', 'position'
        losses: List of dicts with keys: 'element', 'family_member'

    Returns:
        requests.Response object if successful, None if error (logged)

    Note: Must be called within a Flask application context.
    """
    from app.projects.better_signups.models import Event

    def format_element(element):
        """Helper to format element description"""
        if isinstance(element, Event):
            if element.event_type == "date":
                desc = element.event_date.strftime('%B %d, %Y')
            else:
                desc = f"{element.event_datetime.strftime('%B %d, %Y at %I:%M %p')}"
                if element.timezone:
                    desc += f" ({element.timezone})"
            if element.location:
                desc += f" - {element.location}"
        else:
            # It's an Item
            desc = element.name
            if element.description:
                desc += f" - {element.description}"
        return desc

    # Generate list URL
    list_url = url_for('better_signups.view_list', uuid=list_obj.uuid, _external=True)

    subject = f"Lottery Results: {list_obj.name}"

    # Build email content sections
    wins_text = []
    wins_html = []
    for win in wins:
        element_desc = format_element(win['element'])
        deadline_str = win['deadline'].strftime('%B %d at %I:%M %p UTC')
        wins_text.append(
            f"  ✓ {win['family_member'].display_name}: {element_desc}\n"
            f"    Confirm by: {deadline_str}"
        )
        wins_html.append(f"""
            <div style="margin: 10px 0; padding: 15px; background-color: #d4edda; border-radius: 5px; border-left: 4px solid #28a745;">
                <p style="margin: 0 0 5px 0; font-weight: bold; color: #155724;">
                    ✓ {win['family_member'].display_name}
                </p>
                <p style="margin: 0 0 5px 0; color: #155724;">
                    {element_desc}
                </p>
                <p style="margin: 0; font-size: 14px; color: #155724;">
                    <strong>Confirm by: {deadline_str}</strong>
                </p>
            </div>
        """)

    waitlist_text = []
    waitlist_html = []
    for wl in waitlist_positions:
        element_desc = format_element(wl['element'])
        waitlist_text.append(
            f"  • {wl['family_member'].display_name}: {element_desc} (Position #{wl['position']})"
        )
        waitlist_html.append(f"""
            <div style="margin: 10px 0; padding: 10px; background-color: #fff3cd; border-radius: 5px;">
                <p style="margin: 0 0 5px 0; font-weight: bold; color: #856404;">
                    {wl['family_member'].display_name}
                </p>
                <p style="margin: 0; color: #856404;">
                    {element_desc} <strong>(Position #{wl['position']})</strong>
                </p>
            </div>
        """)

    losses_text = []
    losses_html = []
    for loss in losses:
        element_desc = format_element(loss['element'])
        losses_text.append(
            f"  • {loss['family_member'].display_name}: {element_desc}"
        )
        losses_html.append(f"""
            <div style="margin: 5px 0; color: #666;">
                <p style="margin: 0;">
                    {loss['family_member'].display_name}: {element_desc}
                </p>
            </div>
        """)

    # Build text version
    text_content = f"""Hello {user.full_name},

The lottery for '{list_obj.name}' has completed!

"""

    if wins:
        text_content += f"""🎉 CONGRATULATIONS! You won the following spot(s):

{chr(10).join(wins_text)}

⏰ IMPORTANT: You must confirm each spot within 24 hours or it will be offered to the next person on the waitlist.

To confirm your spots:
1. Visit the list: {list_url}
2. Find your pending spots (marked "Pending confirmation")
3. Click "Confirm Your Spot" for each one

"""

    if waitlist_positions:
        text_content += f"""📋 Waitlist Positions:

{chr(10).join(waitlist_text)}

You'll be notified if a spot becomes available!

"""

    if losses:
        text_content += f"""Unfortunately, you did not win the following:

{chr(10).join(losses_text)}

"""

    text_content += """Best regards,
gregmichnikov.com
"""

    # Build HTML version
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #007bff; color: white; padding: 20px; border-radius: 8px 8px 0 0; text-align: center; }}
        .content {{ background-color: #f8f9fa; padding: 20px; }}
        .section {{ margin: 20px 0; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #666; text-align: center; }}
        .btn {{ display: inline-block; padding: 15px 30px; background-color: #28a745; color: #ffffff !important; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px; margin: 20px 0; text-align: center; }}
        .warning-box {{ background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">🎲 Lottery Results</h1>
            <p style="margin: 10px 0 0 0; font-size: 18px;">{list_obj.name}</p>
        </div>
        <div class="content">
            <p>Hello {user.full_name},</p>
            <p><strong>The lottery has completed!</strong> Here are your results:</p>
"""

    if wins:
        html_content += f"""
            <div class="section">
                <h2 style="color: #28a745; margin-top: 0;">🎉 Congratulations! You Won:</h2>
                {''.join(wins_html)}

                <div class="warning-box">
                    <p style="margin: 0 0 10px 0; font-weight: bold;">⏰ Action Required!</p>
                    <p style="margin: 0;">You must confirm each spot within <strong>24 hours</strong> or it will be offered to the next person.</p>
                </div>

                <div style="text-align: center;">
                    <a href="{list_url}" class="btn">View List and Confirm Spots</a>
                </div>
            </div>
"""

    if waitlist_positions:
        html_content += f"""
            <div class="section">
                <h3>📋 Waitlist Positions:</h3>
                {''.join(waitlist_html)}
                <p style="font-size: 14px; color: #666;">You'll be notified if a spot becomes available!</p>
            </div>
"""

    if losses:
        html_content += f"""
            <div class="section">
                <h3>Unfortunately, you did not win:</h3>
                {''.join(losses_html)}
            </div>
"""

    html_content += f"""
        </div>
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
        logger.error(f"Failed to send lottery completion email to {user.email}: {e}")
        return None


def send_lottery_completion_email_creator(creator_user, list_obj, lottery_stats):
    """
    Send lottery completion email to the list creator.

    Args:
        creator_user: User model instance (the list creator)
        list_obj: SignupList model instance (the lottery list)
        lottery_stats: List of dicts with keys: 'element', 'entries_count', 'winners_count', 'waitlist_count'

    Returns:
        requests.Response object if successful, None if error (logged)

    Note: Must be called within a Flask application context.
    """
    from app.projects.better_signups.models import Event

    def format_element(element):
        """Helper to format element description"""
        if isinstance(element, Event):
            if element.event_type == "date":
                return element.event_date.strftime('%B %d, %Y')
            else:
                desc = f"{element.event_datetime.strftime('%B %d, %Y at %I:%M %p')}"
                if element.timezone:
                    desc += f" ({element.timezone})"
                return desc
        else:
            # It's an Item
            return element.name

    # Generate list editor URL
    editor_url = url_for('better_signups.edit_list', uuid=list_obj.uuid, _external=True)

    subject = f"Your Lottery Has Completed: {list_obj.name}"

    # Build stats sections
    stats_text = []
    stats_html = []

    for stat in lottery_stats:
        element_desc = format_element(stat['element'])
        stats_text.append(
            f"  • {element_desc}\n"
            f"    Entries: {stat['entries_count']}\n"
            f"    Winners (pending confirmation): {stat['winners_count']}\n"
            f"    Waitlist: {stat['waitlist_count']}"
        )
        stats_html.append(f"""
            <div style="margin: 15px 0; padding: 15px; background-color: #f8f9fa; border-radius: 5px; border-left: 4px solid #007bff;">
                <p style="margin: 0 0 10px 0; font-weight: bold; color: #007bff;">
                    {element_desc}
                </p>
                <p style="margin: 0; font-size: 14px; color: #666;">
                    <strong>Entries:</strong> {stat['entries_count']}<br>
                    <strong>Winners (pending confirmation):</strong> {stat['winners_count']}<br>
                    <strong>Waitlist:</strong> {stat['waitlist_count']}
                </p>
            </div>
        """)

    text_content = f"""Hello {creator_user.full_name},

Your lottery for '{list_obj.name}' has completed!

Summary:

{chr(10).join(stats_text)}

Winners have been notified by email and have 24 hours to confirm their spots. If they don't confirm, spots will automatically be offered to people on the waitlist.

View and manage your list:
{editor_url}

Best regards,
gregmichnikov.com
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #007bff; color: white; padding: 20px; border-radius: 8px 8px 0 0; text-align: center; }}
        .content {{ background-color: #f8f9fa; padding: 20px; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #666; text-align: center; }}
        .btn {{ display: inline-block; padding: 15px 30px; background-color: #007bff; color: #ffffff !important; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px; margin: 20px 0; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">✓ Lottery Completed</h1>
            <p style="margin: 10px 0 0 0; font-size: 18px;">{list_obj.name}</p>
        </div>
        <div class="content">
            <p>Hello {creator_user.full_name},</p>
            <p><strong>Your lottery has completed!</strong> Here's the summary:</p>

            {''.join(stats_html)}

            <p style="margin-top: 20px;">Winners have been notified by email and have <strong>24 hours</strong> to confirm their spots. If they don't confirm, spots will automatically be offered to people on the waitlist.</p>

            <div style="text-align: center;">
                <a href="{editor_url}" class="btn">Manage Your List</a>
            </div>
        </div>
        <div class="footer">
            <p>Best regards,<br>gregmichnikov.com</p>
        </div>
    </div>
</body>
</html>
"""

    try:
        return send_email(
            to_email=creator_user.email,
            subject=subject,
            text_content=text_content,
            html_content=html_content
        )
    except Exception as e:
        logger.error(f"Failed to send lottery completion email to creator {creator_user.email}: {e}")
        return None
