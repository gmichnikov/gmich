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

# Google Places API (New) — for travel log place search
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

# Cloudflare R2 — for travel log photo storage
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")

# Google Ads Configuration
_google_ads_ids = os.getenv("GOOGLE_ADS_IDS", "")
GOOGLE_ADS_IDS = [id.strip() for id in _google_ads_ids.split(",") if id.strip()]

# Helper project — Mailgun inbound webhook signature verification
MAILGUN_WEBHOOK_SIGNING_KEY = os.getenv("MAILGUN_WEBHOOK_SIGNING_KEY")

# Jinja2 whitespace control - prevents unwanted line breaks in rendered HTML
JINJA2_TRIM_BLOCKS = True
JINJA2_LSTRIP_BLOCKS = True
