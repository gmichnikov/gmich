"""
Better Signups Utilities
Helper functions for the Better Signups project
"""
from app import db
from app.projects.better_signups.models import FamilyMember, ListEditor, Event, Item, Signup, SignupList
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


def get_signup_count(family_member_id, signup_list_id):
    """
    Count the number of signups a family member has in a specific list.
    
    Only counts signups with status 'confirmed' or 'pending_confirmation'.
    Does NOT count cancelled signups or waitlist entries.
    
    Args:
        family_member_id: ID of the family member
        signup_list_id: ID of the signup list
        
    Returns:
        int: Number of active signups for this family member in this list
    """
    # Query for all signups for this family member in this list
    # Need to join through Event or Item to get to the list
    count = 0
    
    # Count event signups
    event_signups = db.session.query(Signup).join(Event).filter(
        Signup.family_member_id == family_member_id,
        Event.list_id == signup_list_id,
        Signup.status.in_(['confirmed', 'pending_confirmation'])
    ).count()
    
    count += event_signups
    
    # Count item signups
    item_signups = db.session.query(Signup).join(Item).filter(
        Signup.family_member_id == family_member_id,
        Item.list_id == signup_list_id,
        Signup.status.in_(['confirmed', 'pending_confirmation'])
    ).count()
    
    count += item_signups
    
    return count


def is_at_limit(family_member_id, signup_list_id):
    """
    Check if a family member has reached the signup limit for a list.
    
    Args:
        family_member_id: ID of the family member
        signup_list_id: ID of the signup list
        
    Returns:
        bool: True if at or above limit, False if below limit or no limit set
    """
    signup_list = SignupList.query.get(signup_list_id)
    
    # If no list found or no limit set, return False (not at limit)
    if not signup_list or signup_list.max_signups_per_member is None:
        return False
    
    # Get current signup count
    current_count = get_signup_count(family_member_id, signup_list_id)
    
    # Check if at or above limit
    return current_count >= signup_list.max_signups_per_member


def can_signup(family_member_id, signup_list_id):
    """
    Check if a family member can sign up for more elements in a list.
    
    This is the inverse of is_at_limit() - returns True if the family member
    is below the limit or if no limit is set.
    
    Args:
        family_member_id: ID of the family member
        signup_list_id: ID of the signup list
        
    Returns:
        bool: True if can sign up for more, False if at limit
    """
    return not is_at_limit(family_member_id, signup_list_id)


def validate_lottery_datetime(lottery_datetime_naive, timezone_str):
    """
    Validate that a lottery datetime is at least 1 hour in the future.
    
    Args:
        lottery_datetime_naive: Naive datetime in creator's timezone
        timezone_str: Timezone string (e.g., "America/New_York")
        
    Returns:
        tuple: (is_valid, error_message, utc_datetime)
            - is_valid: True if valid, False otherwise
            - error_message: Error message if invalid, None if valid
            - utc_datetime: Timezone-aware UTC datetime if valid, None if invalid
    """
    from datetime import datetime, timezone
    
    try:
        # Get the timezone object
        tz = pytz.timezone(timezone_str)
    except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
        return (False, "Invalid timezone", None)
    
    try:
        # Localize the naive datetime to the creator's timezone
        localized_dt = tz.localize(lottery_datetime_naive)
        
        # Convert to UTC
        utc_dt = localized_dt.astimezone(pytz.UTC)
        
        # Get current time in UTC
        now_utc = datetime.now(pytz.UTC)
        
        # Check if at least 1 hour in the future
        time_difference = utc_dt - now_utc
        
        if time_difference.total_seconds() < 3600:  # 3600 seconds = 1 hour
            return (False, "Lottery time must be at least 1 hour from now", None)
        
        return (True, None, utc_dt)
        
    except Exception as e:
        logger.error(f"Error validating lottery datetime: {e}")
        return (False, "Invalid datetime", None)


def send_lottery_completion_emails(signup_list):
    """
    Send lottery completion emails to all participants and the creator.

    Args:
        signup_list: SignupList instance (lottery that just completed)
    """
    from app.projects.better_signups.models import WaitlistEntry, LotteryEntry
    from app.models import User
    from app.utils.email_service import send_lottery_completion_email_participant, send_lottery_completion_email_creator
    from datetime import timedelta

    # Collect data for participant emails
    # Get all users who had lottery entries
    user_entries = {}  # user_id -> {'wins': [], 'waitlist': [], 'losses': []}

    # Get all lottery entries for this list
    all_entries = LotteryEntry.query.filter_by(signup_list_id=signup_list.id).all()

    for entry in all_entries:
        user_id = entry.user_id
        if user_id not in user_entries:
            user_entries[user_id] = {'wins': [], 'waitlist': [], 'losses': []}

    # Categorize each entry as win, waitlist, or loss
    for entry in all_entries:
        element = entry.event if entry.event_id else entry.item
        family_member = entry.family_member
        user_id = entry.user_id

        # Check if won (has pending_confirmation signup)
        if entry.event_id:
            win_signup = Signup.query.filter_by(
                event_id=entry.event_id,
                family_member_id=entry.family_member_id,
                status='pending_confirmation',
                source='lottery'
            ).first()
        else:
            win_signup = Signup.query.filter_by(
                item_id=entry.item_id,
                family_member_id=entry.family_member_id,
                status='pending_confirmation',
                source='lottery'
            ).first()

        if win_signup:
            # Won!
            deadline = win_signup.created_at + timedelta(hours=24)
            user_entries[user_id]['wins'].append({
                'element': element,
                'family_member': family_member,
                'deadline': deadline
            })
        else:
            # Check if on waitlist
            if entry.event_id:
                wl_entry = WaitlistEntry.query.filter_by(
                    element_type='event',
                    element_id=entry.event_id,
                    family_member_id=entry.family_member_id
                ).first()
            else:
                wl_entry = WaitlistEntry.query.filter_by(
                    element_type='item',
                    element_id=entry.item_id,
                    family_member_id=entry.family_member_id
                ).first()

            if wl_entry:
                # On waitlist
                user_entries[user_id]['waitlist'].append({
                    'element': element,
                    'family_member': family_member,
                    'position': wl_entry.position
                })
            else:
                # Did not win
                user_entries[user_id]['losses'].append({
                    'element': element,
                    'family_member': family_member
                })

    # Send emails to all participants
    for user_id, data in user_entries.items():
        try:
            user = User.query.get(user_id)
            if user:
                send_lottery_completion_email_participant(
                    user=user,
                    list_obj=signup_list,
                    wins=data['wins'],
                    waitlist_positions=data['waitlist'],
                    losses=data['losses']
                )
                logger.info(f"Sent lottery completion email to participant {user.email}")
        except Exception as e:
            logger.error(f"Failed to send lottery completion email to user {user_id}: {e}")

    # Collect data for creator email
    lottery_stats = []

    # Get all elements
    events = Event.query.filter_by(list_id=signup_list.id).all()
    items = Item.query.filter_by(list_id=signup_list.id).all()

    for event in events:
        entries_count = LotteryEntry.query.filter_by(event_id=event.id).count()
        winners_count = Signup.query.filter_by(
            event_id=event.id,
            status='pending_confirmation',
            source='lottery'
        ).count()
        waitlist_count = WaitlistEntry.query.filter_by(
            element_type='event',
            element_id=event.id
        ).count()

        lottery_stats.append({
            'element': event,
            'entries_count': entries_count,
            'winners_count': winners_count,
            'waitlist_count': waitlist_count
        })

    for item in items:
        entries_count = LotteryEntry.query.filter_by(item_id=item.id).count()
        winners_count = Signup.query.filter_by(
            item_id=item.id,
            status='pending_confirmation',
            source='lottery'
        ).count()
        waitlist_count = WaitlistEntry.query.filter_by(
            element_type='item',
            element_id=item.id
        ).count()

        lottery_stats.append({
            'element': item,
            'entries_count': entries_count,
            'winners_count': winners_count,
            'waitlist_count': waitlist_count
        })

    # Send email to creator
    try:
        creator = User.query.get(signup_list.creator_id)
        if creator:
            send_lottery_completion_email_creator(
                creator_user=creator,
                list_obj=signup_list,
                lottery_stats=lottery_stats
            )
            logger.info(f"Sent lottery completion email to creator {creator.email}")
    except Exception as e:
        logger.error(f"Failed to send lottery completion email to creator: {e}")


def process_lottery_draws():
    """
    Process all scheduled lotteries that are ready to run.

    Finds lotteries where:
    - lottery_datetime is in the past (will run as soon as scheduler executes after scheduled time)
    - lottery_completed is False
    - lottery_running is False
    
    For each lottery:
    1. Sets lottery_running=True
    2. Processes each element (events chronologically, items by ID)
    3. Randomly selects winners up to spots_available
    4. Respects max_signups_per_member limits
    5. Creates pending_confirmation signups for winners
    6. Adds non-winners to waitlist (randomized order)
    7. Sets lottery_completed=True, lottery_running=False
    
    Returns:
        dict: {
            'processed_count': int,
            'errors': list
        }
    """
    from app.projects.better_signups.models import WaitlistEntry, LotteryEntry
    import random
    
    # Use current time as cutoff - any lottery scheduled in the past will be processed
    # The lottery will run on the next scheduler execution after the scheduled time
    # (typically within 10 minutes if scheduler runs every 10 minutes)
    execution_cutoff = datetime.now(pytz.UTC)
    
    ready_lists = SignupList.query.filter(
        SignupList.is_lottery == True,
        SignupList.lottery_completed == False,
        SignupList.lottery_running == False,
        SignupList.lottery_datetime <= execution_cutoff
    ).all()
    
    if not ready_lists:
        return {'processed_count': 0, 'errors': []}
        
    processed_count = 0
    errors = []
    
    for signup_list in ready_lists:
        try:
            logger.info(f"Starting lottery processing for list '{signup_list.name}' (ID: {signup_list.id})")
            
            # Mark as running to check race conditions (though usually handled by DB lock or single worker)
            signup_list.lottery_running = True
            db.session.commit()
            
            # Gather all elements
            # Process order: Events (chronological), then Items (creation order / ID)
            elements_to_process = []
            
            # Events
            events = Event.query.filter_by(list_id=signup_list.id).all()
            # Sort events: date events by event_date, datetime events by event_datetime
            # We'll normalize to a sort key
            def event_sort_key(e):
                if e.event_type == 'date':
                    return datetime.combine(e.event_date, datetime.min.time())
                return e.event_datetime or datetime.max
            
            events.sort(key=event_sort_key)
            for e in events:
                elements_to_process.append(('event', e))
                
            # Items
            items = Item.query.filter_by(list_id=signup_list.id).order_by(Item.id).all()
            for i in items:
                elements_to_process.append(('item', i))
                
            # Track wins per family member for this lottery run to enforce limits
            # Map: family_member_id -> count of wins in this lottery
            # We also need to know existing signups if we want to be totally strict,
            # but usually limits apply to the total.
            # is_at_limit() checks DB, but since we haven't committed new signups yet,
            # we need to track local wins.
            family_wins_in_run = {}
            
            for element_type, element in elements_to_process:
                # 1. Get all entries for this element
                if element_type == 'event':
                    entries = LotteryEntry.query.filter_by(event_id=element.id).all()
                else:
                    entries = LotteryEntry.query.filter_by(item_id=element.id).all()
                    
                if not entries:
                    continue
                    
                # 2. Shuffle entries for randomness
                random.shuffle(entries)
                
                # 3. Determine available spots
                # For a lottery, it's usually all spots, but maybe creator added some manually?
                # We'll use get_spots_remaining()
                spots_available = element.get_spots_remaining()
                
                # 4. Filter candidates (check limits)
                # We do this optimally by iterating the shuffled list and picking winners
                winners = []
                waitlist_candidates = []
                
                for entry in entries:
                    fm_id = entry.family_member_id

                    # Check if family member is at limit FOR WINNING
                    # During lottery processing, we only count wins in THIS lottery run
                    # (We can't query DB because pending signups haven't been committed yet
                    # and might be visible in the session, causing incorrect counts)
                    # Note: Waitlist positions do NOT count toward the limit

                    # Count wins in this lottery run
                    local_count = family_wins_in_run.get(fm_id, 0)

                    limit = signup_list.max_signups_per_member
                    at_limit = (limit is not None) and (local_count >= limit)

                    if not at_limit and len(winners) < spots_available:
                        # YOU WIN!
                        winners.append(entry)
                        family_wins_in_run[fm_id] = local_count + 1
                    else:
                        # Didn't win (either at limit or no spots left)
                        # Everyone who doesn't win goes on waitlist regardless of limit
                        # PRD: "Family members at their limit can still be on waitlists"
                        waitlist_candidates.append(entry)
                
                # 5. Create Signups for winners
                for win_entry in winners:
                    signup = Signup(
                        user_id=win_entry.user_id,
                        family_member_id=win_entry.family_member_id,
                        status='pending_confirmation',
                        source='lottery'
                    )
                    if element_type == 'event':
                        signup.event_id = element.id
                    else:
                        signup.item_id = element.id
                        
                    db.session.add(signup)
                    
                    # Log it
                    log = LogEntry(
                        project="better_signups",
                        category="Lottery Win",
                        actor_id=win_entry.user_id,
                        description=f"Won lottery for {element.__repr__()} on list {signup_list.name}"
                    )
                    db.session.add(log)
                    
                # 6. Add remaining to Waitlist (if enabled)
                if signup_list.allow_waitlist:
                    # Randomize waitlist candidates too (PRD: "Randomly order them")
                    # They might already be random from the initial shuffle, but shuffle again to be sure
                    # if we had separated them. Actually initial shuffle is enough, but waitlist_candidates
                    # preserves that order.
                    
                    # Current waitlist position start
                    # We need to append to existing waitlist if any (unlikely for new lottery, but possible)
                    current_max_pos = 0
                    if element_type == 'event':
                        last_wl = WaitlistEntry.query.filter_by(element_type='event', element_id=element.id).order_by(WaitlistEntry.position.desc()).first()
                    else:
                        last_wl = WaitlistEntry.query.filter_by(element_type='item', element_id=element.id).order_by(WaitlistEntry.position.desc()).first()
                        
                    if last_wl:
                        current_max_pos = last_wl.position
                        
                    for i, wl_entry in enumerate(waitlist_candidates):
                        position = current_max_pos + i + 1
                        
                        waitlist_item = WaitlistEntry(
                            list_id=signup_list.id,
                            element_type=element_type,
                            element_id=element.id,
                            family_member_id=wl_entry.family_member_id,
                            position=position
                        )
                        db.session.add(waitlist_item)
            
            # Mark complete
            signup_list.lottery_completed = True
            signup_list.lottery_running = False
            db.session.commit()

            processed_count += 1
            logger.info(f"Completed lottery for list '{signup_list.name}'")

            # Send emails after successful completion
            try:
                send_lottery_completion_emails(signup_list)
            except Exception as email_error:
                logger.error(f"Error sending lottery completion emails: {email_error}")
            
        except Exception as e:
            db.session.rollback()
            # Try to clear the running flag if possible
            try:
                signup_list.lottery_running = False
                db.session.commit()
            except:
                pass
                
            error_msg = f"Error processing lottery for list {signup_list.id}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            
    return {
        'processed_count': processed_count,
        'errors': errors
    }
