"""
Better Signups Utilities
Helper functions for the Better Signups project
"""
from app import db
from app.projects.better_signups.models import FamilyMember


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

