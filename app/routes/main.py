from flask import Blueprint, render_template
from flask_login import current_user

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        email = current_user.email
        return render_template('index.html', logged_in=True, email=email)
    else:
        return render_template('index.html', logged_in=False)

@main_bp.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404