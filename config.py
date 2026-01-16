import os

DATABASE_URL = os.getenv("DATABASE_URL").replace("postgres://", "postgresql://", 1)
SQLALCHEMY_DATABASE_URI = DATABASE_URL

SECRET_KEY = os.getenv("SECRET_KEY")

# Server configuration for URL generation (needed for CLI commands that send emails)
# SERVER_NAME = os.getenv("SERVER_NAME")
# PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", "https")

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# Google Ads Configuration
_google_ads_ids = os.getenv("GOOGLE_ADS_IDS", "")
GOOGLE_ADS_IDS = [id.strip() for id in _google_ads_ids.split(",") if id.strip()]

# Jinja2 whitespace control - prevents unwanted line breaks in rendered HTML
JINJA2_TRIM_BLOCKS = True
JINJA2_LSTRIP_BLOCKS = True
