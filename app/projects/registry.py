"""
Project Registry - Centralized configuration for all projects in the hub.

To add a new project:
1. Create the project directory and files
2. Register the blueprint in app/__init__.py
3. Add an entry to PROJECTS list below

Project Types:
- 'project': Standalone project that appears on homepage
- 'category': Group of projects that links to a listing page
- 'external': External link that opens in new tab

For projects that belong to a category, add 'parent' field with category ID.
"""

PROJECTS = [
    {
        'id': 'todo',
        'name': 'Todo App',
        'description': 'A simple and elegant todo list application to manage your tasks',
        'url': '/todo',
        'auth_required': True,
        'status': 'active',
        'type': 'project',
        'order': 1
    },
    {
        'id': 'calculator',
        'name': 'Calculator',
        'description': 'Pure JavaScript calculator with basic arithmetic operations',
        'url': '/calculator',
        'auth_required': False,
        'status': 'active',
        'type': 'project',
        'order': 2
    },
    {
        'id': 'simple_games',
        'name': 'Simple Games',
        'description': 'Classic memory and logic games - Mastermind, Simon Says, and more!',
        'url': '/games',
        'auth_required': False,
        'status': 'active',
        'type': 'category',
        'icon': '🎮',
        'order': 3
    },
    {
        'id': 'mastermind',
        'name': 'Mastermind',
        'description': 'Classic code-breaking game - crack the 4-color code in 10 guesses',
        'url': '/mastermind',
        'auth_required': False,
        'status': 'active',
        'type': 'project',
        'parent': 'simple_games',
        'order': 301  # Sub-order within parent
    },
    {
        'id': 'simon_says',
        'name': 'Simon Says',
        'description': 'Test your memory with this classic color sequence game',
        'url': '/simon-says',
        'auth_required': False,
        'status': 'active',
        'type': 'project',
        'parent': 'simple_games',
        'order': 302
    },
    {
        'id': 'tic_tac_toe',
        'name': 'Tic-Tac-Toe',
        'description': 'Classic two-player game with fun emoji themes',
        'url': '/tic-tac-toe',
        'auth_required': False,
        'status': 'active',
        'type': 'project',
        'parent': 'simple_games',
        'order': 303
    },
    {
        'id': 'connect4',
        'name': 'Connect 4',
        'description': 'Drop discs to connect four in a row - with doom detection!',
        'url': '/connect4',
        'auth_required': False,
        'status': 'active',
        'type': 'project',
        'parent': 'simple_games',
        'order': 304
    },
    {
        'id': 'algebra_snake',
        'name': 'Algebra Snake',
        'description': 'Classic snake game meets math - eat the correct answers to grow!',
        'url': '/algebra-snake',
        'auth_required': False,
        'status': 'active',
        'type': 'project',
        'parent': 'simple_games',
        'order': 305
    },
    {
        'id': 'gm_84_plus',
        'name': 'GM-84 Plus',
        'description': 'Advanced graphing calculator - plot equations, zoom, animate, and explore!',
        'url': 'https://gmichnikov.github.io/gm-84-plus/',
        'auth_required': False,
        'status': 'active',
        'type': 'external',
        'order': 4
    },
    {
        'id': 'estimate_pi',
        'name': 'Estimate Pi',
        'description': 'Throw virtual darts at a dartboard to estimate π using Monte Carlo simulation',
        'url': 'https://gmichnikov.github.io/estimate-pi/',
        'auth_required': False,
        'status': 'active',
        'type': 'external',
        'order': 5
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


def get_homepage_items(is_authenticated):
    """
    Get items to display on the homepage (projects and categories, but not child projects).
    For use in templates to show what a user can access.
    
    Args:
        is_authenticated (bool): Whether the user is logged in
        
    Returns:
        list: Items with 'available' flag set based on auth status
    """
    items = []
    for project in get_all_projects():
        # Skip projects that have a parent (they're shown in category pages)
        if project.get('parent'):
            continue
            
        project_copy = project.copy()
        # Mark as available if active AND (no auth required OR user is authenticated)
        project_copy['available'] = (
            project['status'] == 'active' and 
            (not project['auth_required'] or is_authenticated)
        )
        items.append(project_copy)
    
    return items


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


def get_children_of_category(category_id, is_authenticated=False):
    """
    Get all child projects belonging to a specific category.
    
    Args:
        category_id (str): The category ID
        is_authenticated (bool): Whether the user is logged in
        
    Returns:
        list: Child projects with 'available' flag set
    """
    children = []
    for project in get_all_projects():
        if project.get('parent') == category_id:
            project_copy = project.copy()
            project_copy['available'] = (
                project['status'] == 'active' and 
                (not project['auth_required'] or is_authenticated)
            )
            children.append(project_copy)
    
    return sorted(children, key=lambda x: x['order'])
