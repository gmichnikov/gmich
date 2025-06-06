import os

DATABASE_URL = os.getenv('DATABASE_URL').replace("postgres://", "postgresql://", 1)
SQLALCHEMY_DATABASE_URI = DATABASE_URL

SECRET_KEY = os.getenv('SECRET_KEY')