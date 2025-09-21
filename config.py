import os
from datetime import timedelta

# Base directory
basedir = os.path.abspath(os.path.dirname(__file__))

# Security
SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'
SECURITY_PASSWORD_SALT = os.environ.get('SECURITY_PASSWORD_SALT') or 'dev-salt-change-in-production'

# Database
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'app.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Email configuration
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', 'on', '1']
MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')

# Admin settings
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
SUPPORT_EMAIL = os.environ.get('SUPPORT_EMAIL', 'support@example.com')

# App settings
APP_NAME = 'Tarang Web Interface'
APP_URL = os.environ.get('APP_URL', 'http://localhost:5000')

# Session settings
PERMANENT_SESSION_LIFETIME = timedelta(days=7)

# MFA settings
MFA_ISSUER = os.environ.get('MFA_ISSUER', 'Tarang-Web')

# LogIN session timeout (in minutes)
LOGIN_SESSION_TIMEOUT = int(os.environ.get('LOGIN_SESSION_TIMEOUT', '30'))

# Login attempts before account is locked
MAX_LOGIN_ATTEMPTS = int(os.environ.get('MAX_LOGIN_ATTEMPTS', '5'))
ACCOUNT_LOCKOUT_DURATION = int(os.environ.get('ACCOUNT_LOCKOUT_DURATION', '15'))  # in minutes

# Password requirements
MIN_PASSWORD_LENGTH = 12
REQUIRE_SPECIAL_CHAR = True
REQUIRE_NUMBER = True
REQUIRE_UPPERCASE = True
REQUIRE_LOWERCASE = True

# Password reset token expiration (in hours)
PASSWORD_RESET_EXPIRATION = 24

# CSRF protection
WTF_CSRF_ENABLED = True

# File upload settings
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'h5', 'dat', 'csv', 'json'}

# Logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
LOG_FILE = os.environ.get('LOG_FILE', 'app.log')

# Caching
CACHE_TYPE = 'simple'  # Can be 'simple', 'redis', 'memcached', etc.
CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes

# Session configuration
SESSION_TYPE = 'filesystem'
SESSION_PERMANENT = True
SESSION_USE_SIGNER = True

# Security headers
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ['true', 'on', '1']
REMEMBER_COOKIE_HTTPONLY = True
REMEMBER_COOKIE_SECURE = os.environ.get('REMEMBER_COOKIE_SECURE', 'false').lower() in ['true', 'on', '1']

# Rate limiting
RATELIMIT_DEFAULT = '200 per day;50 per hour;10 per minute'
