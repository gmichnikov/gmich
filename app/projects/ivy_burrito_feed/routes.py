from flask import Blueprint, render_template
from app.utils.logging import log_project_visit

ivy_burrito_feed_bp = Blueprint('ivy_burrito_feed', __name__, 
                                 template_folder='templates')

@ivy_burrito_feed_bp.route('/')
def index():
    """Display the Ivy Burrito Feed game"""
    log_project_visit('ivy_burrito_feed', 'Ivy Burrito Feed')
    return render_template('ivy_burrito_feed.html')
