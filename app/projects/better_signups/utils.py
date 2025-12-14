"""
Better Signups Utilities
Helper functions for the Better Signups project
"""
from app import db
from app.projects.better_signups.models import FamilyMember, ListEditor, Event, Item, Signup
from app.models import LogEntry
from urllib.parse import urlencode
import pytz
from datetime import timedelta, datetime
import logging

logger = logging.getLogger(__name__)


def ensure_self_family_member(user):
    """
    Ensure a user has a "self" family member record.
    Creates one if it doesn't exist, updates the name if it does.
    
    Args:
        user: User instance
        
    Returns:
        FamilyMember: The "self" family member record
    """
    self_member = FamilyMember.query.filter_by(
        user_id=user.id,
        is_self=True
    ).first()
    
    if not self_member:
        # Create "self" family member
        self_member = FamilyMember(
            user_id=user.id,
            display_name=user.full_name,
            is_self=True
        )
        db.session.add(self_member)
        db.session.commit()
    elif self_member.display_name != user.full_name:
        # Update name if user's full_name changed
        self_member.display_name = user.full_name
        db.session.commit()
    
    return self_member


def link_pending_editor_invitations(user):
    """
    Link any pending editor invitations (ListEditor records with email but no user_id)
    to the newly registered/logged-in user.
    
    Args:
        user: User instance
        
    Returns:
        int: Number of invitations linked
    """
    email = user.email.lower()
    
    # Find all pending invitations for this email
    pending_invitations = ListEditor.query.filter_by(
        email=email,
        user_id=None
    ).all()
    
    if not pending_invitations:
        return 0
    
    # Link them to this user
    for invitation in pending_invitations:
        invitation.user_id = user.id
    
    db.session.commit()
    
    return len(pending_invitations)


def get_google_calendar_url(event, list_name, user=None):
    """
    Generate a Google Calendar URL for adding an event to Google Calendar.
    
    Args:
        event: Event instance (date or datetime type)
        list_name: Name of the signup list
        user: User instance (required for date events to get timezone)
        
    Returns:
        str: Google Calendar URL, or None if event is invalid
    """
    # Handle date-only events
    if event.event_type == "date":
        if not event.event_date or not user:
            return None
        
        # Get user's timezone
        try:
            user_tz = pytz.timezone(user.time_zone) if user.time_zone else pytz.UTC
        except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
            user_tz = pytz.UTC
        
        # Create datetime at noon in user's timezone
        # event.event_date is a date object, so we need to combine it with a time
        from datetime import time
        noon_time = time(12, 0, 0)  # 12:00:00
        noon_datetime = datetime.combine(event.event_date, noon_time)
        noon_local = user_tz.localize(noon_datetime)
        
        # Convert to UTC for Google Calendar
        start_utc = noon_local.astimezone(pytz.UTC)
        
        # Default to 1 hour duration for date events
        end_utc = start_utc + timedelta(hours=1)
        
    # Handle datetime events
    elif event.event_type == "datetime":
        if not event.event_datetime:
            return None
        
        # Get timezone - use event timezone or default to UTC
        try:
            event_tz = (
                pytz.timezone(event.timezone) if event.timezone else pytz.UTC
            )
        except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
            # Fallback to UTC if timezone is invalid
            event_tz = pytz.UTC
        
        # Localize the datetime to the event's timezone
        # event_datetime is stored as naive datetime, so we need to localize it
        if event.event_datetime.tzinfo is None:
            # Naive datetime - localize it
            localized_start = event_tz.localize(event.event_datetime)
        else:
            # Already timezone-aware - convert to event timezone first, then UTC
            localized_start = event.event_datetime.astimezone(event_tz)
        
        # Convert to UTC for Google Calendar
        start_utc = localized_start.astimezone(pytz.UTC)
        
        # Calculate end time
        if event.duration_minutes:
            end_utc = start_utc + timedelta(minutes=event.duration_minutes)
        else:
            # Default to 1 hour if no duration specified
            end_utc = start_utc + timedelta(hours=1)
    else:
        # Unknown event type
        return None
    
    # Format dates for Google Calendar (YYYYMMDDTHHMMSSZ format)
    start_str = start_utc.strftime("%Y%m%dT%H%M%SZ")
    end_str = end_utc.strftime("%Y%m%dT%H%M%SZ")
    
    # Build event title
    title = list_name
    if event.description:
        title = f"{list_name}: {event.description[:50]}"  # Limit description in title
    
    # Build description
    description_parts = [f"Signup for: {list_name}"]
    if event.description:
        description_parts.append(f"\n\n{event.description}")
    
    description = "\n".join(description_parts)
    
    # Build URL parameters
    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{start_str}/{end_str}",
        "details": description,
    }
    
    # Add location if available
    if event.location:
        params["location"] = event.location
    
    # Build and return URL
    base_url = "https://calendar.google.com/calendar/render"
    return f"{base_url}?{urlencode(params)}"


def check_has_eligible_swap_targets(signup):
    """
    Check if a signup has any eligible swap targets in its list.
    
    A swap target is eligible if:
    - It's a different element (not the one the user is signed up for)
    - It's FULL (no available spots remaining)
    - It has at least one signup
    - The user's family member is NOT already signed up for it
    
    Args:
        signup: Signup instance
        
    Returns:
        bool: True if there are eligible swap targets, False otherwise
    """
    # Get the list
    signup_list = signup.event.list if signup.event else signup.item.list
    
    if signup_list.list_type == "events":
        # Count events that are full, have signups, and user isn't already signed up for
        current_event_id = signup.event_id
        eligible_events = Event.query.filter(
            Event.list_id == signup_list.id,
            Event.id != current_event_id
        ).all()
        
        for event in eligible_events:
            if event.get_spots_remaining() == 0 and event.get_spots_taken() > 0:
                # Check if user is already signed up for this event
                existing = Signup.query.filter_by(
                    event_id=event.id,
                    family_member_id=signup.family_member_id,
                ).first()
                if not existing:
                    return True
    else:  # items
        # Count items that are full, have signups, and user isn't already signed up for
        current_item_id = signup.item_id
        eligible_items = Item.query.filter(
            Item.list_id == signup_list.id,
            Item.id != current_item_id
        ).all()
        
        for item in eligible_items:
            if item.get_spots_remaining() == 0 and item.get_spots_taken() > 0:
                # Check if user is already signed up for this item
                existing = Signup.query.filter_by(
                    item_id=item.id,
                    family_member_id=signup.family_member_id,
                ).first()
                if not existing:
                    return True
    
    return False


def process_expired_pending_confirmations():
    """
    Process expired pending_confirmation signups (older than 24 hours).
    
    This function:
    1. Finds all pending_confirmation signups older than 24 hours
    2. Deletes them
    3. Offers the spot to the next person on the waitlist (if applicable)
    4. Logs all actions
    
    Returns:
        dict: {
            'processed_count': int,  # Number of expired signups removed
            'cascade_count': int,    # Number of spots offered to next person
            'errors': list           # List of error messages (if any)
        }
    """
    from app.projects.better_signups.models import SignupList
    
    # Avoid circular import - import here
    from app.projects.better_signups.routes import offer_spot_to_next_in_waitlist
    
    expiration_cutoff = datetime.utcnow() - timedelta(hours=24)
    
    expired_signups = Signup.query.filter(
        Signup.status == "pending_confirmation",
        Signup.created_at <= expiration_cutoff,
    ).all()
    
    if not expired_signups:
        return {'processed_count': 0, 'cascade_count': 0, 'errors': []}
    
    processed_count = 0
    cascade_count = 0
    errors = []
    
    for signup in expired_signups:
        try:
            # Get element info before deleting
            if signup.event_id:
                element_type = "event"
                element_id = signup.event_id
                event = Event.query.get(element_id)
                if not event:
                    errors.append(f"Signup {signup.id}: Event {element_id} not found")
                    continue
                if event.event_type == "date":
                    element_desc = f"event date: {event.event_date.strftime('%B %d, %Y')}"
                else:
                    element_desc = f"event datetime: {event.event_datetime.strftime('%B %d, %Y at %I:%M %p')}"
            elif signup.item_id:
                element_type = "item"
                element_id = signup.item_id
                item = Item.query.get(element_id)
                if not item:
                    errors.append(f"Signup {signup.id}: Item {element_id} not found")
                    continue
                element_desc = f"item: {item.name}"
            else:
                errors.append(f"Signup {signup.id} has no event or item")
                continue
            
            family_member_name = signup.family_member.display_name if signup.family_member else "Unknown"
            list_name = signup.event.list.name if signup.event else signup.item.list.name
            list_uuid = signup.event.list.uuid if signup.event else signup.item.list.uuid
            list_id = signup.event.list_id if signup.event else signup.item.list_id
            
            logger.info(
                f"Processing expired pending confirmation for {family_member_name} "
                f"on list '{list_name}', {element_desc}"
            )
            
            # Delete the expired signup
            db.session.delete(signup)
            
            # Log the expiration
            log_entry = LogEntry(
                project="better_signups",
                category="Waitlist Expiration",
                actor_id=signup.user_id,
                description=f"Pending confirmation expired for {family_member_name} on list '{list_name}' (UUID: {list_uuid}), {element_desc}. Spot offered at {signup.created_at.strftime('%B %d, %Y at %I:%M %p')}.",
            )
            db.session.add(log_entry)
            
            # Commit the deletion and log
            db.session.commit()
            processed_count += 1
            
            # Check if list allows waitlist and offer to next person
            signup_list = SignupList.query.get(list_id)
            
            if signup_list and signup_list.allow_waitlist:
                cascade_result = offer_spot_to_next_in_waitlist(element_type, element_id)
                if cascade_result:
                    cascade_count += 1
                    next_family_member = cascade_result["family_member"]
                    logger.info(
                        f"Cascade after expiration: offered spot to {next_family_member.display_name} "
                        f"(user {cascade_result['user'].id})"
                    )
                    # Send email notification
                    try:
                        from app.projects.better_signups.routes import send_waitlist_offer_email
                        send_waitlist_offer_email(cascade_result)
                    except Exception as email_error:
                        logger.error(f"Failed to send waitlist offer email: {email_error}")
                else:
                    logger.info(f"Waitlist empty for {element_type} {element_id}, spot now available to all")
        
        except Exception as e:
            db.session.rollback()
            error_msg = f"Error processing signup {signup.id}: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
            continue
    
    return {
        'processed_count': processed_count,
        'cascade_count': cascade_count,
        'errors': errors
    }
