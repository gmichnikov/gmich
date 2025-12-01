# Projects Directory

This directory contains all the projects hosted on my site.

## Directory Structure

```
projects/
├── registry.py           # Centralized project configuration
├── todo/                 # Example: Full-stack app with auth & database
│   ├── __init__.py
│   ├── routes.py
│   ├── models.py
│   ├── forms.py
│   ├── templates/
│   └── static/
└── calculator/           # Example: Pure JavaScript static app
    ├── __init__.py
    ├── routes.py
    ├── templates/
    └── static/
```

## Adding a New Project

### 1. Create Project Directory

```bash
mkdir -p app/projects/your_project/{templates,static}
```

### 2. Create Basic Files

**`__init__.py`** (makes it a package):

```python
# Your Project package
```

**`routes.py`** (Flask blueprint):

```python
from flask import Blueprint, render_template

your_project_bp = Blueprint('your_project', __name__,
                            template_folder='templates',
                            static_folder='static')

@your_project_bp.route('/')
def index():
    return render_template('your_project.html')
```

### 3. Register Blueprint

In `app/__init__.py`, add:

```python
from app.projects.your_project.routes import your_project_bp
app.register_blueprint(your_project_bp, url_prefix='/your-project')
```

### 4. Add to Registry

In `app/projects/registry.py`, add your project to the `PROJECTS` list:

```python
{
    'id': 'your_project',
    'name': 'Your Project Name',
    'description': 'Brief description of what your project does',
    'icon': '🎯',  # Pick an emoji icon
    'url': '/your-project',
    'auth_required': False,  # True if requires login
    'status': 'active',  # or 'coming_soon'
    'order': 5  # Display order on homepage
}
```

### 5. Create Templates & Static Files

- Add your HTML templates in `templates/`
- Add CSS/JS/images in `static/`
- Templates can extend `base.html` for consistent navigation

## Project Types

### Full-Stack Projects (like Todo)

- Use database models (`models.py`)
- Use Flask forms (`forms.py`)
- Require authentication
- Server-side logic

### Static JavaScript Projects (like Calculator)

- No backend logic needed
- Pure client-side JavaScript
- Can be public (no auth required)
- Flask just serves the files

## Registry Configuration

### Project Fields

| Field           | Type    | Description                                   |
| --------------- | ------- | --------------------------------------------- |
| `id`            | string  | Unique identifier (use snake_case)            |
| `name`          | string  | Display name shown to users                   |
| `description`   | string  | Brief description (1-2 sentences)             |
| `icon`          | string  | Emoji icon for visual appeal                  |
| `url`           | string  | Route URL (must match blueprint registration) |
| `auth_required` | boolean | True if login is required to access           |
| `status`        | string  | 'active' or 'coming_soon'                     |
| `order`         | integer | Display order on homepage (lower = first)     |

### Helper Functions

```python
from app.projects.registry import (
    get_all_projects,           # All projects sorted by order
    get_active_projects,        # Only active projects
    get_project_by_id,          # Get specific project
    get_projects_by_auth,       # Filter by auth requirement
    get_projects_for_user       # For templates (handles availability)
)
```

## Best Practices

1. **Keep projects isolated** - Each project should be self-contained
2. **Use blueprints** - Never mix routes between projects
3. **Consistent naming** - Use snake_case for IDs and URLs
4. **Update registry first** - Add to registry before coding
5. **Test both states** - Test logged-in and logged-out views
6. **Match your theme** - Use the site's color scheme and styling
7. **Mobile-friendly** - Always test responsive design

## Examples

See existing projects:

- **Todo App** - Full-stack with auth, database, forms
- **Calculator** - Pure JavaScript, no auth, static files

## Questions?

Check the main app documentation or existing project code for reference.
