import os

DATABASE_URL = os.getenv('DATABASE_URL').replace("postgres://", "postgresql://", 1)
SQLALCHEMY_DATABASE_URI = DATABASE_URL

SECRET_KEY = os.getenv('SECRET_KEY')

# Jinja2 whitespace control - prevents unwanted line breaks in rendered HTML
JINJA2_TRIM_BLOCKS = True
JINJA2_LSTRIP_BLOCKS = True