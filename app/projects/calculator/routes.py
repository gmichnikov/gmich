from flask import Blueprint, render_template

calculator_bp = Blueprint('calculator', __name__, 
                         template_folder='templates',
                         static_folder='static')

@calculator_bp.route('/')
def index():
    """Display the calculator - pure JavaScript, no backend logic needed"""
    return render_template('calculator.html')

