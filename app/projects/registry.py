"""
Project Registry - Centralized configuration for all projects in the hub.

To add a new project:
1. Create the project directory and files
2. Register the blueprint in app/__init__.py
3. Add an entry to PROJECTS list below
"""

PROJECTS = [
    {
        'id': 'todo',
        'name': 'Todo App',
        'description': 'A simple and elegant todo list application to manage your tasks',
        'icon': '✓',
        'url': '/todo',
        'auth_required': True,
        'status': 'active',
        'order': 1
    },
    {
        'id': 'calculator',
        'name': 'Calculator',
        'description': 'Pure JavaScript calculator with basic arithmetic operations',
        'icon': '🔢',
        'url': '/calculator',
        'auth_required': False,
        'status': 'active',
        'order': 2
    },
    {
        'id': 'notes',
        'name': 'Notes',
        'description': 'Take and organize notes with markdown support',
        'icon': '📝',
        'url': '/notes',
        'auth_required': True,
        'status': 'coming_soon',
        'order': 3
    },
    {
        'id': 'weather',
        'name': 'Weather App',
        'description': 'Check current weather and forecasts for any location',
        'icon': '🌤',
        'url': '/weather',
        'auth_required': False,
        'status': 'coming_soon',
        'order': 4
    }
]


def get_all_projects():
    """
    Get all projects from the registry.
    
    Returns:
        list: List of all projects sorted by order
    """
    return sorted(PROJECTS, key=lambda x: x['order'])


def get_active_projects():
    """
    Get only active (available) projects.
    
    Returns:
        list: List of active projects
    """
    return [p for p in get_all_projects() if p['status'] == 'active']


def get_project_by_id(project_id):
    """
    Get a specific project by its ID.
    
    Args:
        project_id (str): The project ID to look up
        
    Returns:
        dict: Project data or None if not found
    """
    return next((p for p in PROJECTS if p['id'] == project_id), None)


def get_projects_by_auth(auth_required=None):
    """
    Get projects filtered by authentication requirement.
    
    Args:
        auth_required (bool): True for auth-required projects, False for public, None for all
        
    Returns:
        list: Filtered list of projects
    """
    if auth_required is None:
        return get_all_projects()
    return [p for p in get_all_projects() if p['auth_required'] == auth_required]


def get_projects_for_user(is_authenticated):
    """
    Get projects appropriate for a user's authentication status.
    For use in templates to show what projects a user can access.
    
    Args:
        is_authenticated (bool): Whether the user is logged in
        
    Returns:
        list: Projects with 'available' flag set based on auth status
    """
    projects = []
    for project in get_all_projects():
        project_copy = project.copy()
        # Mark as available if active AND (no auth required OR user is authenticated)
        project_copy['available'] = (
            project['status'] == 'active' and 
            (not project['auth_required'] or is_authenticated)
        )
        projects.append(project_copy)
    
    return projects

