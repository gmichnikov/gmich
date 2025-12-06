import os

DATABASE_URL = os.getenv("DATABASE_URL").replace("postgres://", "postgresql://", 1)
SQLALCHEMY_DATABASE_URI = DATABASE_URL

SECRET_KEY = os.getenv("SECRET_KEY")

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
# Base URL for OAuth redirects (e.g., https://yourdomain.com)
# If not set, will fall back to using request headers
OAUTH_REDIRECT_BASE_URL = os.getenv("OAUTH_REDIRECT_BASE_URL")

# Jinja2 whitespace control - prevents unwanted line breaks in rendered HTML
JINJA2_TRIM_BLOCKS = True
JINJA2_LSTRIP_BLOCKS = True
