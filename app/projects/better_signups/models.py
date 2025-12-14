"""
Better Signups Models
Database models for the Better Signups project
"""

from datetime import datetime
import uuid as uuid_lib
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class SignupList(db.Model):
    """A list containing either events or items for signups"""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    list_password_hash = db.Column(db.String(128), nullable=True)
    accepting_signups = db.Column(db.Boolean, default=True)
    list_type = db.Column(db.String(20), nullable=False)  # 'events' or 'items'
    uuid = db.Column(db.String(36), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    creator = db.relationship(
        "User",
        foreign_keys=[creator_id],
        backref=db.backref("created_signup_lists", lazy=True),
    )
    editors = db.relationship(
        "ListEditor",
        backref=db.backref("list", lazy=True),
        cascade="all, delete-orphan",
    )
    events = db.relationship(
        "Event", backref=db.backref("list", lazy=True), cascade="all, delete-orphan"
    )
    items = db.relationship(
        "Item", backref=db.backref("list", lazy=True), cascade="all, delete-orphan"
    )

    def set_list_password(self, password):
        """Hash and store the list password"""
        self.list_password_hash = generate_password_hash(password)

    def check_list_password(self, password):
        """Check if the provided password matches the list password"""
        if not self.list_password_hash:
            return False
        return check_password_hash(self.list_password_hash, password)

    def user_has_access(self, user):
        """Check if a user has been granted access to this password-protected list"""
        if not self.list_password_hash:
            return True  # No password protection = everyone has access

        # Creators always have access to their own lists
        if self.creator_id == user.id:
            return True

        # Check if user has been granted access
        from app.projects.better_signups.models import ListAccess

        access_grant = ListAccess.query.filter_by(
            user_id=user.id, list_id=self.id
        ).first()
        return access_grant is not None

    def grant_user_access(self, user):
        """Grant a user permanent access to this list (after successful password entry)"""
        from app.projects.better_signups.models import ListAccess

        # Use get_or_create pattern to avoid duplicates
        access_grant = ListAccess.query.filter_by(
            user_id=user.id, list_id=self.id
        ).first()

        if not access_grant:
            access_grant = ListAccess(user_id=user.id, list_id=self.id)
            db.session.add(access_grant)
            db.session.commit()

        return access_grant

    def generate_uuid(self):
        """Generate a unique UUID for this list"""
        self.uuid = str(uuid_lib.uuid4())
        return self.uuid

    def is_editor(self, user):
        """Check if a user is an editor (creator is always an editor)"""
        if self.creator_id == user.id:
            return True
        # Check by user_id or by email (for pending invitations)
        return any(
            editor.user_id == user.id
            or (editor.email and editor.email.lower() == user.email.lower())
            for editor in self.editors
        )

    def __repr__(self):
        return f"<SignupList {self.id}: {self.name}>"


class ListEditor(db.Model):
    """Additional editors for a signup list (creator is always an editor)

    Can have either a user_id (if user exists) or just an email (pending invitation).
    When a user signs up with an invited email, the user_id will be linked.
    """

    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey("signup_list.id"), nullable=False)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=True
    )  # Nullable for pending invitations
    email = db.Column(
        db.String(60), nullable=True
    )  # Email for pending invitations or as backup
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Unique constraint: either (list_id, user_id) or (list_id, email) must be unique
    # We'll enforce this in application logic since SQL doesn't support OR in unique constraints well
    __table_args__ = (
        db.UniqueConstraint("list_id", "user_id", name="unique_list_user"),
        db.UniqueConstraint("list_id", "email", name="unique_list_email"),
    )

    # Relationships
    user = db.relationship("User", backref=db.backref("list_editorships", lazy=True))

    def get_display_email(self):
        """Get the email to display (from user if exists, otherwise from email field)"""
        if self.user:
            return self.user.email
        return self.email

    def __repr__(self):
        if self.user_id:
            return f"<ListEditor list_id={self.list_id} user_id={self.user_id}>"
        return f"<ListEditor list_id={self.list_id} email={self.email}>"


class FamilyMember(db.Model):
    """Family members associated with a user account"""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    display_name = db.Column(db.String(200), nullable=False)  # Single full name
    is_self = db.Column(db.Boolean, default=False)  # True for user's "self" record
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Note: We enforce one "self" per user in application logic (see ensure_self_family_member).
    # For PostgreSQL, we'll add a partial unique index in a migration to ensure only one
    # is_self=True record per user at the database level.
    # Multiple non-self family members are allowed per user.
    __table_args__ = ()

    # Relationships
    user = db.relationship("User", backref=db.backref("family_members", lazy=True))
    signups = db.relationship("Signup", backref=db.backref("family_member", lazy=True))

    def __repr__(self):
        return f"<FamilyMember {self.id}: {self.display_name} (user_id={self.user_id})>"


class Event(db.Model):
    """An event (date or datetime) in a signup list"""

    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey("signup_list.id"), nullable=False)
    event_type = db.Column(db.String(20), nullable=False)  # 'date' or 'datetime'
    event_date = db.Column(db.Date, nullable=True)  # For date-only
    event_datetime = db.Column(db.DateTime, nullable=True)  # For datetime
    timezone = db.Column(db.String(50), nullable=True)  # For datetime only
    duration_minutes = db.Column(db.Integer, nullable=True)  # For datetime only
    location = db.Column(db.String(200), nullable=True)
    location_is_link = db.Column(
        db.Boolean, nullable=False, default=True
    )  # Whether location should link to Google Maps
    description = db.Column(db.Text, nullable=True)
    spots_available = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    signups = db.relationship(
        "Signup", backref=db.backref("event", lazy=True), cascade="all, delete-orphan"
    )

    def get_active_signups(self):
        """Get all signups for this event"""
        return self.signups

    def get_spots_taken(self):
        """Get the number of spots currently taken"""
        return len(self.get_active_signups())

    def get_spots_remaining(self):
        """Get the number of spots remaining"""
        return max(0, self.spots_available - self.get_spots_taken())

    def get_end_datetime(self):
        """Get the end datetime for datetime events (start + duration)"""
        if (
            self.event_type == "datetime"
            and self.event_datetime
            and self.duration_minutes
        ):
            from datetime import timedelta

            return self.event_datetime + timedelta(minutes=self.duration_minutes)
        return None

    def __repr__(self):
        if self.event_type == "date":
            return f"<Event {self.id}: {self.event_date}>"
        else:
            return f"<Event {self.id}: {self.event_datetime}>"


class Item(db.Model):
    """An item in a signup list"""

    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey("signup_list.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    spots_available = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    signups = db.relationship(
        "Signup", backref=db.backref("item", lazy=True), cascade="all, delete-orphan"
    )

    def get_active_signups(self):
        """Get all signups for this item"""
        return self.signups

    def get_spots_taken(self):
        """Get the number of spots currently taken"""
        return len(self.get_active_signups())

    def get_spots_remaining(self):
        """Get the number of spots remaining"""
        return max(0, self.spots_available - self.get_spots_taken())

    def __repr__(self):
        return f"<Item {self.id}: {self.name}>"


class ListAccess(db.Model):
    """Tracks which users have been granted access to password-protected lists"""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    list_id = db.Column(db.Integer, db.ForeignKey("signup_list.id"), nullable=False)
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship("User", backref=db.backref("list_accesses", lazy=True))
    signup_list = db.relationship(
        "SignupList", backref=db.backref("access_grants", lazy=True)
    )

    # Unique constraint to prevent duplicate access grants
    __table_args__ = (
        db.UniqueConstraint("user_id", "list_id", name="unique_user_list_access"),
    )

    def __repr__(self):
        return f"<ListAccess user_id={self.user_id} list_id={self.list_id}>"


class Signup(db.Model):
    """A signup for an event or item"""

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"), nullable=True)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    family_member_id = db.Column(
        db.Integer, db.ForeignKey("family_member.id"), nullable=False
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint(
            "(event_id IS NOT NULL AND item_id IS NULL) OR (event_id IS NULL AND item_id IS NOT NULL)"
        ),
        db.UniqueConstraint("event_id", "family_member_id", name="unique_event_signup"),
        db.UniqueConstraint("item_id", "family_member_id", name="unique_item_signup"),
    )

    # Relationships
    user = db.relationship("User", backref=db.backref("signups", lazy=True))

    def __repr__(self):
        element = (
            f"event_id={self.event_id}" if self.event_id else f"item_id={self.item_id}"
        )
        return f"<Signup {self.id}: {element} family_member_id={self.family_member_id}>"


class SwapRequest(db.Model):
    """A swap request - user wants to swap FROM one signup TO one or more target elements"""

    id = db.Column(db.Integer, primary_key=True)
    requestor_signup_id = db.Column(
        db.Integer, db.ForeignKey("signup.id"), nullable=False
    )
    list_id = db.Column(db.Integer, db.ForeignKey("signup_list.id"), nullable=False)
    requestor_family_member_id = db.Column(
        db.Integer, db.ForeignKey("family_member.id"), nullable=False
    )
    status = db.Column(db.String(20), nullable=False, default="pending")  # 'pending', 'completed', 'cancelled'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    completed_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    # Relationships
    requestor_signup = db.relationship(
        "Signup",
        foreign_keys=[requestor_signup_id],
        backref=db.backref("swap_requests_as_requestor", lazy=True),
    )
    list = db.relationship("SignupList", backref=db.backref("swap_requests", lazy=True))
    requestor_family_member = db.relationship(
        "FamilyMember",
        foreign_keys=[requestor_family_member_id],
        backref=db.backref("swap_requests_as_requestor", lazy=True),
    )
    completed_by_user = db.relationship(
        "User",
        foreign_keys=[completed_by_user_id],
        backref=db.backref("swap_requests_completed", lazy=True),
    )
    targets = db.relationship(
        "SwapRequestTarget",
        backref=db.backref("swap_request", lazy=True),
        cascade="all, delete-orphan",
    )
    tokens = db.relationship(
        "SwapToken",
        backref=db.backref("swap_request", lazy=True),
        cascade="all, delete-orphan",
    )

    def is_pending(self):
        """Check if this swap request is still pending"""
        return self.status == "pending"

    def __repr__(self):
        return f"<SwapRequest {self.id}: signup_id={self.requestor_signup_id} status={self.status}>"


class SwapRequestTarget(db.Model):
    """Target elements for a swap request (allows one swap request to target multiple elements)"""

    id = db.Column(db.Integer, primary_key=True)
    swap_request_id = db.Column(
        db.Integer, db.ForeignKey("swap_request.id"), nullable=False
    )
    target_element_id = db.Column(db.Integer, nullable=False)  # ID of event or item
    target_element_type = db.Column(
        db.String(20), nullable=False
    )  # 'event' or 'item'

    # Unique constraint: one swap request can't target the same element twice
    __table_args__ = (
        db.UniqueConstraint(
            "swap_request_id",
            "target_element_id",
            "target_element_type",
            name="unique_swap_request_target",
        ),
    )

    def get_target_element(self):
        """Get the actual Event or Item object"""
        if self.target_element_type == "event":
            from app.projects.better_signups.models import Event
            return Event.query.get(self.target_element_id)
        else:
            from app.projects.better_signups.models import Item
            return Item.query.get(self.target_element_id)

    def __repr__(self):
        return f"<SwapRequestTarget {self.id}: swap_request_id={self.swap_request_id} {self.target_element_type}_id={self.target_element_id}>"


class SwapToken(db.Model):
    """Token for a swap link - one per eligible family member + target element combo"""

    id = db.Column(db.Integer, primary_key=True)
    swap_request_id = db.Column(
        db.Integer, db.ForeignKey("swap_request.id"), nullable=False
    )
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    recipient_signup_id = db.Column(
        db.Integer, db.ForeignKey("signup.id"), nullable=False
    )
    recipient_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    target_element_id = db.Column(db.Integer, nullable=False)  # ID of event or item this token is for
    target_element_type = db.Column(db.String(20), nullable=False)  # 'event' or 'item'
    is_used = db.Column(db.Boolean, default=False, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    recipient_signup = db.relationship(
        "Signup",
        foreign_keys=[recipient_signup_id],
        backref=db.backref("swap_tokens_as_recipient", lazy=True),
    )
    recipient_user = db.relationship(
        "User",
        foreign_keys=[recipient_user_id],
        backref=db.backref("swap_tokens_received", lazy=True),
    )

    @staticmethod
    def generate_token():
        """Generate a unique token for a swap link"""
        return secrets.token_urlsafe(48)  # 64 characters when base64 encoded

    def get_target_element(self):
        """Get the actual Event or Item object that this token is for"""
        if self.target_element_type == "event":
            from app.projects.better_signups.models import Event
            return Event.query.get(self.target_element_id)
        else:
            from app.projects.better_signups.models import Item
            return Item.query.get(self.target_element_id)

    def mark_as_used(self):
        """Mark this token as used"""
        if not self.is_used:
            self.is_used = True
            self.used_at = datetime.utcnow()

    def __repr__(self):
        return f"<SwapToken {self.id}: token={self.token[:8]}... is_used={self.is_used}>"
