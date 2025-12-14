"""
Better Signups Utilities
Helper functions for the Better Signups project
"""
from app import db
from app.projects.better_signups.models import FamilyMember, ListEditor, Event, Item, Signup
from urllib.parse import urlencode
import pytz
from datetime import timedelta, datetime


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
