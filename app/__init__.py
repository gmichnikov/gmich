from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
import os
import markdown
import logging

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app():
    # Validate required environment variables
    required_vars = ['DATABASE_URL', 'SECRET_KEY', 'ADMIN_EMAIL']
    for var in required_vars:
        if not os.getenv(var):
            raise ValueError(f"Required environment variable {var} is not set")
    
    app = Flask(__name__)
    app.config.from_object('config')
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # Register blueprints
    from app.routes.main import main_bp
    from app.core.auth import auth_bp
    from app.core.admin import admin_bp
    from app.projects.mastermind.routes import mastermind_bp
    from app.projects.simon_says.routes import simon_says_bp
    from app.projects.tic_tac_toe.routes import tic_tac_toe_bp
    from app.projects.connect4.routes import connect4_bp
    from app.projects.algebra_snake.routes import algebra_snake_bp
    from app.projects.spanish_vocab_invaders.routes import spanish_vocab_invaders_bp
    from app.projects.sorry_cards.routes import sorry_cards_bp
    from app.projects.sushi_go.routes import sushi_go_bp
    from app.projects.chatbot.routes import chatbot_bp
    from app.projects.ask_many_llms.routes import bp as ask_many_llms_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(mastermind_bp, url_prefix='/mastermind')
    app.register_blueprint(simon_says_bp, url_prefix='/simon-says')
    app.register_blueprint(tic_tac_toe_bp, url_prefix='/tic-tac-toe')
    app.register_blueprint(connect4_bp, url_prefix='/connect4')
    app.register_blueprint(algebra_snake_bp, url_prefix='/algebra-snake')
    app.register_blueprint(spanish_vocab_invaders_bp, url_prefix='/spanish-vocab-invaders')
    app.register_blueprint(sorry_cards_bp, url_prefix='/sorry-cards')
    app.register_blueprint(sushi_go_bp, url_prefix='/sushi-go')
    app.register_blueprint(chatbot_bp, url_prefix='/chatbot')
    app.register_blueprint(ask_many_llms_bp)  # Has its own url_prefix defined
    
    # Import models to ensure they're known to Flask-SQLAlchemy
    from app.models import User, LogEntry
    from app.projects.chatbot.models import ChatMessage
    from app.projects.ask_many_llms.models import LLMQuestion, LLMResponse
    
    # Register markdown filter for Ask Many LLMs templates
    @app.template_filter('markdown')
    def markdown_filter(text):
        return markdown.markdown(text, extensions=['fenced_code', 'tables'])
    
    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    return app