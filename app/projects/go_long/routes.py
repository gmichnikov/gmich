from flask import Blueprint, render_template

go_long_bp = Blueprint('go_long', __name__, 
                        template_folder='templates',
                        static_folder='static',
                        static_url_path='/projects/go_long/static')

@go_long_bp.route('/')
def index():
    return render_template('go_long.html')
