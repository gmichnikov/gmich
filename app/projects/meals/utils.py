from app.projects.meals.models import MealsFamilyGroup, MealsFamilyMember

def get_user_family_groups(user):
    """
    Get all family groups that a user is a member of.
    """
    memberships = MealsFamilyMember.query.filter_by(user_id=user.id).all()
    return [m.family_group for m in memberships]

def is_user_in_group(user, group_id):
    """
    Check if a user is a member of a specific family group.
    """
    membership = MealsFamilyMember.query.filter_by(
        user_id=user.id, 
        family_group_id=group_id
    ).first()
    return membership is not None
