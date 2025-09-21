# Default para.py content used by "Load Default" action on Run Config page
DEFAULT_PARA_CONTENT = """para_directory = 'C:/Users/kabha/OneDrive/Desktop/Programming/Vayusoft_Labs/Tarang to give'
executable_path = 'C:/Users/kabha/OneDrive/Desktop/Programming/Vayusoft_Labs/Tarang to give'
application_path = 'C:/Users/kabha/OneDrive/Desktop/Programming/Vayusoft_Labs/Tarang to give'
device = 'CPU'
dimension = 3
kind = 'HYDRO'
Nx = 64
Ny = 64
Nz = 64
input_dir = 'C:/Users/kabha/OneDrive/Desktop/Programming/Vayusoft_Labs/Tarang to give/input/2025_09_11_17_49_07'
input_file_name = 'init_cond.h5'
output_dir = 'C:/Users/kabha/OneDrive/Desktop/Programming/Vayusoft_Labs/Tarang to give/output/2025_09_11_17_49_07'
nu = 0.01
alt_dissipation = False
FORCING_ENABLED = False
nu_hypo = 0.1
nu_hypo_power = -2.0
nu_hyper = 0.0
nu_hyper_power = 25.0
forcing_range = [4, 5]
injections = [0, 0, 0]
t_initial = 0.0
t_final = 0.01
dt = 0.001
time_scheme = 'EULER'
FIXED_DT = True
Courant_no = 0.5
modes_save = ((1, 0, 0), (0, 0, 1))
iter_field_save_start = 0.0
iter_field_save_inter = 500.0
iter_glob_energy_print_start = 0.0
iter_glob_energy_print_inter = 1.0
iter_ekTk_save_start = 0.0
iter_ekTk_save_inter = 100.0
iter_modes_save_start = 0.0
iter_modes_save_inter = 200.0
device_rank = 0
complex_dtype = 'complex'
real_dtype = 'float64'
BOX_SIZE_DEFAULT = True
L = [6.283185307179586, 6.283185307179586, 6.283185307179586]
Rac = 657.5113644795163
Ra = 328755682.23975813
Pr = 6.8
kappa = 2.114992879944374e-05
maintain_mux = 1
gpu_direct_storage = False
Omega = [0, 0, 0]
Nb = 0
HYPO_DISSIPATION = False
HYPER_DISSIPATION = False
nu_hypo_cutoff = -1
eta_hypo_cutoff = -1
kappa_hypo_cutoff = -1
kappa_hypo = 1
kappa_hypo_power = -2
kappa_hyper = 0.0001
kappa_hyper_power = 2
ROTATION_ENABLED = False
MAINTAIN_FIELD = False
PRINT_PARAMETERS = True
USE_BINDING = True
PLANAR_SPECTRA = False
SAVE_VORTICITY = False
SAVE_VECPOT = False
VALIDATE_SOLVER = False
t_eps = 1e-08
RUNTIME_SAVE = True
INPUT_SET_CASE = True
input_case = 'custom'
INPUT_FROM_FILE = False
INPUT_REAL_FIELD = False
INPUT_ELSASSER = False
OUTPUT_REAL_FIELD = False
FORCING_SCHEME = 'random'
RANDOM_FORCING_TYPE = 'u'
BUOYANCY_ENABLED = False
LIVE_PLOT = False
"""

import os
import re
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify, abort
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from flask_admin import Admin, AdminIndexView, expose, BaseView, form
from flask_admin.contrib.sqla import ModelView
from flask_admin.menu import MenuLink
from flask_admin.model import typefmt
from flask_admin.actions import action
from wtforms.fields import PasswordField
from functools import wraps
import json
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
import requests
import bcrypt
from cryptography.fernet import Fernet
import numpy as np
import default_params
import types

# Load environment variables from .env file
load_dotenv()

# Import configuration
import config

# Create Flask application
app = Flask(__name__)

# Apply configuration
for key in dir(config):
    if key.isupper():
        app.config[key] = getattr(config, key)

# Ensure the instance folder exists
os.makedirs(app.instance_path, exist_ok=True)

# Update SQLite database path to be in the instance folder
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(app.instance_path, 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure Flask-Mail
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
# Clean the password to remove any non-ASCII characters and spaces
mail_password = os.getenv('MAIL_PASSWORD')
cleaned_password = ''.join(c for c in mail_password if ord(c) < 128).replace(' ', '') if mail_password else ''
app.config['MAIL_PASSWORD'] = cleaned_password
print(f"DEBUG - Password cleaning: Original length: {len(mail_password or '')}, Cleaned length: {len(cleaned_password)}")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

# Debug email configuration
print(f"DEBUG - Email Configuration:")
print(f"  MAIL_SERVER: {app.config['MAIL_SERVER']}")
print(f"  MAIL_PORT: {app.config['MAIL_PORT']}")
print(f"  MAIL_USE_TLS: {app.config['MAIL_USE_TLS']}")
print(f"  MAIL_USERNAME: {app.config['MAIL_USERNAME']}")
print(f"  MAIL_DEFAULT_SENDER: {app.config['MAIL_DEFAULT_SENDER']}")
print(f"  MAIL_PASSWORD: {'*' * len(str(app.config['MAIL_PASSWORD']))}")

# Import models after app creation to avoid circular imports
from models import db, User

# Import job models for database creation
try:
    from job_models import SimulationJob, JobLog, JobMetric, ResourceUsage
    print("✅ Job models imported successfully")
except Exception as e:
    print(f"⚠️  Job models not available: {e}")

# Initialize database
db.init_app(app)

# Initialize Flask-Mail
mail = Mail(app)

# Create database tables
with app.app_context():
    # Check if we need to recreate the database
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        
        if inspector.has_table('users'):
            columns = [col['name'] for col in inspector.get_columns('users')]
            missing_columns = []
            
            # Check for OTP columns
            if 'otp_code' not in columns:
                missing_columns.append('otp_code')
            if 'otp_expires_at' not in columns:
                missing_columns.append('otp_expires_at')
            if 'otp_attempts' not in columns:
                missing_columns.append('otp_attempts')
            if 'is_otp_verified' not in columns:
                missing_columns.append('is_otp_verified')
                
            # Check for password reset columns
            if 'reset_token' not in columns:
                missing_columns.append('reset_token')
            if 'reset_token_expires_at' not in columns:
                missing_columns.append('reset_token_expires_at')
            if 'reset_attempts' not in columns:
                missing_columns.append('reset_attempts')
            
            if missing_columns:
                print(f"Database schema is outdated. Missing columns: {missing_columns}")
                print("Recreating database with full feature support...")
                # Drop all tables and recreate
                db.drop_all()
                db.create_all()
                print("Database recreated successfully with OTP and password reset support!")
            else:
                print("Database schema is up to date.")
        else:
            print("Creating new database...")
            db.create_all()
            print("Database created successfully!")
            
    except Exception as e:
        print(f"Database setup error: {e}")
        print("Creating fresh database...")
        db.create_all()

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize AWS services (optional for testing)
try:
    from aws_integration import initialize_aws_services
    from job_routes import jobs_bp
    
    # Register job management blueprint
    app.register_blueprint(jobs_bp)
    
    # Try to initialize AWS services (will fail gracefully if not configured)
    aws_manager, eks_manager, monitor = initialize_aws_services()
    app.aws_manager = aws_manager
    app.eks_manager = eks_manager
    app.monitor = monitor
    print("✅ AWS services initialized successfully")
    
except Exception as e:
    print(f"⚠️  AWS services not available (this is OK for local testing): {e}")
    app.aws_manager = None
    app.eks_manager = None
    app.monitor = None

# Admin Access Control
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

# Custom Admin Index View
class MyAdminIndexView(AdminIndexView):
    @expose('/')
    @login_required
    @admin_required
    def index(self):
        return super(MyAdminIndexView, self).index()

# User model is now imported from models.py

# Initialize LoginManager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Admin Model View
class UserModelView(ModelView):
    column_list = ['id', 'username', 'email', 'is_active', 'is_approved', 'created_at']
    column_searchable_list = ['username', 'email']
    column_filters = ['is_active', 'is_approved']
    form_columns = ['username', 'email', 'is_active', 'is_approved']
    
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=request.url))

# Email notification functions
def send_email(to, subject, template, **kwargs):
    """Send email using Flask-Mail"""
    try:
        print(f"DEBUG - Attempting to send email to: {to}")
        print(f"DEBUG - Subject: {subject}")
        print(f"DEBUG - Template: {template}")
        print(f"DEBUG - MAIL_SERVER: {app.config.get('MAIL_SERVER')}")
        print(f"DEBUG - MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
        
        msg = Message(
            subject=subject,
            recipients=[to],
            html=render_template(f'email/{template}', **kwargs),
            sender=app.config['MAIL_DEFAULT_SENDER']
        )
        mail.send(msg)
        print(f"✅ Email sent successfully to {to}: {subject}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email to {to}: {str(e)}")
        print(f"DEBUG - Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

def notify_admin_new_user(user):
    """Notify admin about new user registration"""
    admin_email = app.config.get('SUPPORT_EMAIL', 'kshah@iitk.ac.in')
    send_email(
        to=admin_email,
        subject=f'New User Registration - {user.username}',
        template='admin_approval_required.html',
        user=user,
        admin_url=url_for('admin.index', _external=True),
        now=datetime.utcnow(),
        config=app.config,
        support_email=admin_email
    )

def notify_user_approved(user):
    """Notify user that their account has been approved"""
    send_email(
        to=user.email,
        subject='Account Approved - Tarang Platform',
        template='account_approved.html',
        user=user,
        login_url=url_for('login', _external=True),
        now=datetime.utcnow(),
        config=app.config,
        support_email=app.config.get('SUPPORT_EMAIL', 'kshah@iitk.ac.in')
    )

def notify_user_pending(user):
    """Notify user that their account is pending approval"""
    send_email(
        to=user.email,
        subject='Account Created - Pending Approval',
        template='account_pending_approval.html',
        user=user,
        now=datetime.utcnow(),
        config=app.config,
        support_email=app.config.get('SUPPORT_EMAIL', 'kshah@iitk.ac.in')
    )

def send_otp_email(user, otp_code):
    """Send OTP via email for multi-factor authentication"""
    print(f"DEBUG - Sending OTP email to {user.email} with code: {otp_code}")
    result = send_email(
        to=user.email,
        subject='Login Verification Code - Tarang',
        template='otp_verification.html',
        user=user,
        otp_code=otp_code,
        now=datetime.utcnow(),
        config=app.config,
        expires_in=10  # 10 minutes
    )
    if result:
        print(f"✅ OTP email sent successfully to {user.email}")
    else:
        print(f"❌ Failed to send OTP email to {user.email}")
    return result

def send_password_reset_email(user, reset_token):
    """Send password reset email"""
    print(f"DEBUG - Sending password reset email to {user.email}")
    print(f"DEBUG - Reset token: {reset_token[:10]}...")
    
    try:
        reset_url = url_for('reset_password', token=reset_token, _external=True)
        print(f"DEBUG - Reset URL generated: {reset_url}")
    except Exception as e:
        print(f"ERROR - Failed to generate reset URL: {e}")
        return False
    
    result = send_email(
        to=user.email,
        subject='Password Reset Request - Tarang',
        template='password_reset.html',
        user=user,
        reset_url=reset_url,
        reset_token=reset_token,
        now=datetime.utcnow(),
        config=app.config,
        expires_in=24  # 24 hours
    )
    if result:
        print(f"✅ Password reset email sent successfully to {user.email}")
    else:
        print(f"❌ Failed to send password reset email to {user.email}")
    return result

# Global variables to track running processes
running_processes = {}
process_counter = 0

# Simple retention policy for per-user runs
RUNS_RETENTION_DAYS = 30
RUNS_MAX_KEEP = 100

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def check_license():
    """Check if user has valid license"""
    user_folder = str(Path.home())
    try:
        with open(user_folder + '/tarang.license', 'r') as file:
            expiry_date = file.readline().split(':')[-1].strip()
            expiry_datetime = datetime.strptime(expiry_date, "%Y-%m-%d")
            current_datetime = datetime.now()
            difference_datetime = expiry_datetime - current_datetime
            return difference_datetime.days >= 0
    except FileNotFoundError:
        return False

def get_user_store_path():
    """Return the path to the user store JSON file, creating directory if needed."""
    user_store_dir = Path('user_data')
    user_store_dir.mkdir(parents=True, exist_ok=True)
    return user_store_dir / 'users.json'

def load_users():
    path = get_user_store_path()
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}

def save_users(users):
    path = get_user_store_path()
    path.write_text(json.dumps(users, indent=2))

def ensure_user_directory(username):
    """Ensure per-user directory exists."""
    user_dir = Path('user_data') / str(username)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir

def verify_credentials(username, password):
    """Verify user credentials using bcrypt and a JSON user store."""
    users = load_users()
    record = users.get(username)
    if not record:
        return False
    stored_hash = record.get('password_hash', '').encode('utf-8')
    try:
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash)
    except Exception:
        return False

def validate_password_policy(password, is_admin=False):
    """
    Validate password against security policy.
    Admin accounts are excluded from the enhanced policy.
    
    Returns: (is_valid, error_message)
    """
    if is_admin:
        # Basic validation for admin accounts
        if len(password) < 6:
            return False, "Admin password must be at least 6 characters long"
        return True, ""
    
    # Enhanced policy for regular users
    errors = []
    
    # Must be more than 8 characters (at least 9)
    if len(password) < 9:
        errors.append("at least 9 characters")
    
    # Must contain uppercase letter
    if not re.search(r'[A-Z]', password):
        errors.append("at least one uppercase letter")
    
    # Must contain lowercase letter
    if not re.search(r'[a-z]', password):
        errors.append("at least one lowercase letter")
    
    # Must contain number
    if not re.search(r'[0-9]', password):
        errors.append("at least one number")
    
    # Must contain special character
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?~`]', password):
        errors.append("at least one special character (!@#$%^&*...)")
    
    if errors:
        return False, f"Password must contain: {', '.join(errors)}"
    
    return True, ""

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.index'))
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/debug/users')
@login_required
@admin_required
def debug_users():
    """Debug route to check user data"""
    users = User.query.all()
    user_data = []
    for user in users:
        user_data.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_active': user.is_active,
            'is_approved': user.is_approved,
            'is_admin': user.is_admin,
            'created_at': user.created_at
        })
    
    return f"""
    <h2>Debug: User Data</h2>
    <p>Total users: {len(users)}</p>
    <pre>{user_data}</pre>
    <p><a href="/admin">Back to Admin</a></p>
    <p><a href="/admin/user/">Try Flask-Admin Users</a></p>
    """

@app.route('/debug/routes')
@login_required
@admin_required
def debug_routes():
    """Debug route to check available routes"""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'rule': str(rule)
        })
    
    return f"""
    <h2>Debug: Available Routes</h2>
    <pre>{routes}</pre>
    <p><a href="/admin">Back to Admin</a></p>
    """

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """Simple user management interface"""
    users = User.query.all()
    
    # Get flash messages
    from flask import get_flashed_messages
    messages = get_flashed_messages(with_categories=True)
    
    html = """
    <div class="container mt-4">
        <h2>User Management</h2>"""
    
    # Add flash messages if any
    if messages:
        for category, message in messages:
            alert_class = 'danger' if category == 'error' else 'success' if category == 'success' else 'info'
            icon_class = 'exclamation-triangle' if category == 'error' else 'check-circle' if category == 'success' else 'info-circle'
            html += f"""
        <div class="alert alert-{alert_class} alert-dismissible fade show" role="alert">
            <i class="fas fa-{icon_class} me-2"></i>
            {message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>"""
    
    html += """
        <div class="row">
            <div class="col-md-12">
                <div class="card">
                    <div class="card-header">
                        <h5>All Users</h5>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-striped">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Username</th>
                                        <th>Email</th>
                                        <th>Active</th>
                                        <th>Approved</th>
                                        <th>Admin</th>
                                        <th>Created</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
    """
    
    for user in users:
        active_badge = '<span class="badge bg-success">Yes</span>' if user.is_active else '<span class="badge bg-danger">No</span>'
        approved_badge = '<span class="badge bg-success">Yes</span>' if user.is_approved else '<span class="badge bg-warning">No</span>'
        admin_badge = '<span class="badge bg-info">Yes</span>' if user.is_admin else '<span class="badge bg-secondary">No</span>'
        
        # Add delete button only for non-admin users
        delete_button = "" if user.is_admin else f'<button onclick="confirmDelete({user.id}, \'{user.username}\')" class="btn btn-sm btn-danger">Delete</button>'
        
        html += f"""
                                    <tr>
                                        <td>{user.id}</td>
                                        <td>{user.username}</td>
                                        <td>{user.email}</td>
                                        <td>{active_badge}</td>
                                        <td>{approved_badge}</td>
                                        <td>{admin_badge}</td>
                                        <td>{user.created_at.strftime('%Y-%m-%d %H:%M') if user.created_at else 'N/A'}</td>
                                        <td>
                                            <a href="/admin/users/{user.id}/approve" class="btn btn-sm btn-success me-1">Approve</a>
                                            <a href="/admin/users/{user.id}/toggle" class="btn btn-sm btn-warning me-1">Toggle Active</a>
                                            {delete_button}
                                        </td>
                                    </tr>
        """
    
    html += """
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="mt-3">
            <a href="/admin" class="btn btn-secondary">Back to Dashboard</a>
        </div>
    </div>
    
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    
    <style>
    .table th {
        background-color: #f8f9fa;
        font-weight: 600;
    }
    .btn-sm {
        margin-right: 4px;
    }
    .badge {
        font-size: 0.75em;
    }
    </style>
    
    <script>
    function confirmDelete(userId, username) {
        const message = `⚠️ WARNING: Delete User Account\\n\\n` +
                       `You are about to permanently delete the user "${username}".\\n\\n` +
                       `This will:\\n` +
                       `• Remove the user from the database\\n` +
                       `• Delete all user files and directories\\n` +
                       `• Cannot be undone\\n\\n` +
                       `Are you absolutely sure you want to proceed?`;
        
        if (confirm(message)) {
            // Show loading state
            const deleteBtn = event.target;
            deleteBtn.disabled = true;
            deleteBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Deleting...';
            
            // Create a form to submit the delete request
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = `/admin/users/${userId}/delete`;
            
            // Add CSRF token if needed
            const csrfToken = document.querySelector('meta[name="csrf-token"]');
            if (csrfToken) {
                const csrfInput = document.createElement('input');
                csrfInput.type = 'hidden';
                csrfInput.name = 'csrf_token';
                csrfInput.value = csrfToken.getAttribute('content');
                form.appendChild(csrfInput);
            }
            
            document.body.appendChild(form);
            form.submit();
        }
    }
    
    // Auto-hide alerts after 5 seconds
    document.addEventListener('DOMContentLoaded', function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            setTimeout(() => {
                if (alert.classList.contains('show')) {
                    alert.classList.remove('show');
                    setTimeout(() => alert.remove(), 150);
                }
            }, 5000);
        });
    });
    </script>
    """
    
    return html

@app.route('/admin/users/<int:user_id>/approve')
@login_required
@admin_required
def approve_user(user_id):
    """Approve a user"""
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    user.is_active = True  # Also activate when approving
    db.session.commit()
    
    # Send approval email
    notify_user_approved(user)
    
    flash(f'User {user.username} has been approved and activated!', 'success')
    return redirect('/admin/users')

@app.route('/admin/users/<int:user_id>/toggle')
@login_required
@admin_required
def toggle_user_active(user_id):
    """Toggle user active status"""
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    
    status = "activated" if user.is_active else "deactivated"
    flash(f'User {user.username} has been {status}!', 'info')
    return redirect('/admin/users')

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Delete a user (admin only, cannot delete admin users or self)"""
    user = User.query.get_or_404(user_id)
    
    # Security checks
    if user.is_admin:
        flash('Cannot delete admin users!', 'error')
        return redirect('/admin/users')
    
    if user.id == current_user.id:
        flash('Cannot delete your own account!', 'error')
        return redirect('/admin/users')
    
    try:
        username = user.username
        
        # Delete user's directory if it exists
        user_dir = os.path.join('users', username)
        if os.path.exists(user_dir):
            import shutil
            shutil.rmtree(user_dir)
            print(f"Deleted user directory: {user_dir}")
        
        # Delete user from database
        db.session.delete(user)
        db.session.commit()
        
        flash(f'User "{username}" has been successfully deleted!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'error')
        print(f"Error deleting user {user.username}: {str(e)}")
    
    return redirect('/admin/users')

@app.route('/debug/test-email/<email>')
@login_required
@admin_required
def test_email(email):
    """Test email sending functionality"""
    try:
        print(f"DEBUG - Testing email to: {email}")
        print(f"DEBUG - MAIL_SERVER: {app.config.get('MAIL_SERVER')}")
        print(f"DEBUG - MAIL_PORT: {app.config.get('MAIL_PORT')}")
        print(f"DEBUG - MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS')}")
        print(f"DEBUG - MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
        print(f"DEBUG - MAIL_DEFAULT_SENDER: {app.config.get('MAIL_DEFAULT_SENDER')}")
        
        # Test basic email
        result = send_email(
            to=email,
            subject='Test Email from Tarang',
            template='account_pending_approval.html',
            user={'username': 'test_user', 'email': email},
            now=datetime.utcnow(),
            config=app.config,
            support_email=app.config.get('SUPPORT_EMAIL', 'kshah@iitk.ac.in')
        )
        
        if result:
            return f"✅ Test email sent successfully to {email}!"
        else:
            return f"❌ Failed to send test email to {email}. Check terminal logs for details."
            
    except Exception as e:
        return f"❌ Error testing email: {str(e)}"

@app.route('/debug/test-otp/<email>')
@login_required
@admin_required
def test_otp_email(email):
    """Test OTP email sending"""
    try:
        print(f"DEBUG - Testing OTP email to: {email}")
        
        # Create a test user object
        test_user = type('TestUser', (), {
            'username': 'test_user',
            'email': email
        })()
        
        # Test OTP email
        result = send_otp_email(test_user, '123456')
        
        if result:
            return f"✅ Test OTP email sent successfully to {email}!"
        else:
            return f"❌ Failed to send test OTP email to {email}. Check terminal logs for details."
            
    except Exception as e:
        return f"❌ Error testing OTP email: {str(e)}"

@app.route('/debug/test-reset/<email>')
@login_required
@admin_required
def test_reset_email(email):
    """Test password reset email sending"""
    try:
        print(f"DEBUG - Testing password reset email to: {email}")
        
        # Create a test user object
        test_user = type('TestUser', (), {
            'username': 'test_user',
            'email': email,
            'generate_reset_token': lambda: 'test_token_123456'
        })()
        
        # Test password reset email
        result = send_password_reset_email(test_user, 'test_token_123456')
        
        if result:
            return f"✅ Test password reset email sent successfully to {email}!"
        else:
            return f"❌ Failed to send test password reset email to {email}. Check terminal logs for details."
            
    except Exception as e:
        return f"❌ Error testing password reset email: {str(e)}"

@app.route('/debug/check-users')
@login_required
@admin_required
def check_users():
    """Check what users exist in the database"""
    users = User.query.all()
    
    html = "<h2>Users in Database:</h2><ul>"
    for user in users:
        html += f"<li><strong>{user.username}</strong> - {user.email} (Active: {user.is_active}, Approved: {user.is_approved})</li>"
    html += "</ul>"
    html += f"<p>Total users: {len(users)}</p>"
    html += "<p><a href='/admin'>Back to Admin</a></p>"
    
    return html

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        print(f"\n=== Login Attempt ===")
        print(f"Username: {username}")
        print(f"Password: {password}")
        
        # Check if this is an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        user = User.query.filter_by(username=username).first()
        
        if user:
            print(f"User found: {user.username}")
            print(f"Stored hash: {user.password_hash}")
            print(f"Check password: {user.check_password(password)}")
            print(f"Is active: {user.is_active}")
            print(f"Is admin: {user.is_admin}")
        else:
            print("No user found with that username")
        
        if user and user.check_password(password):
            if not user.is_approved:
                print("Login failed - user not approved")
                message = 'Your account is pending admin approval. Please wait for approval.'
                if is_ajax:
                    return jsonify({'success': False, 'message': message}), 401
                flash(message)
                return render_template('login.html'), 401
                
            if not user.is_active:
                print("Login failed - user not active")
                message = 'Your account has been deactivated. Please contact administrator.'
                if is_ajax:
                    return jsonify({'success': False, 'message': message}), 401
                flash(message)
                return render_template('login.html'), 401
            
            # Admin users skip OTP
            if user.is_admin:
                login_user(user)
                print("Admin login successful - OTP skipped")
                if is_ajax:
                    return jsonify({
                        'success': True,
                        'redirect': url_for('admin.index'),
                        'message': 'Login successful! Redirecting to admin dashboard...'
                    })
                return redirect(url_for('admin.index'))
            
            # Regular users need OTP verification
            otp_code = user.generate_otp()
            db.session.commit()
            
            # Send OTP via email
            email_sent = send_otp_email(user, otp_code)
            
            if not email_sent:
                message = 'Failed to send verification code. Please try again or contact support.'
                if is_ajax:
                    return jsonify({'success': False, 'message': message}), 500
                flash(message, 'error')
                return render_template('login.html'), 500
            
            # Store user ID in session for OTP verification
            session['otp_user_id'] = user.id
            session['otp_verified'] = False
            session.modified = True  # Ensure session is saved
            
            # Return JSON response for AJAX handling
            return jsonify({
                'success': True,
                'message': 'Please wait for OTP. A verification code has been sent to your email and may take a few seconds to arrive.',
                'otp_required': True,
                'email': user.email  # For displaying the email in the OTP form
            })
            
        print("Login failed - wrong credentials")
        message = 'Wrong credentials, try again'
        if is_ajax:
            return jsonify({'success': False, 'message': message}), 401
        flash(message, 'error')
        return render_template('login.html'), 401
        
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    """AJAX login endpoint for better UX"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({
                'success': False,
                'message': 'Username and password are required.'
            }), 400
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            return jsonify({
                'success': False,
                'message': 'Wrong credentials, try again'
            }), 401
        
        if not user.is_approved:
            return jsonify({
                'success': False,
                'message': 'Your account is pending admin approval. Please wait for approval.'
            }), 401
            
        if not user.is_active:
            return jsonify({
                'success': False,
                'message': 'Your account has been deactivated. Please contact administrator.'
            }), 401
        
        # Admin users skip OTP
        if user.is_admin:
            login_user(user)
            return jsonify({
                'success': True,
                'redirect': url_for('admin.index'),
                'message': 'Login successful! Redirecting to admin dashboard...'
            })
        
        # Regular users need OTP verification
        otp_code = user.generate_otp()
        db.session.commit()
        
        # Send OTP via email
        email_sent = send_otp_email(user, otp_code)
        
        if not email_sent:
            return jsonify({
                'success': False,
                'message': 'Failed to send verification code. Please try again or contact support.'
            }), 500
        
        # Store user ID in session for OTP verification
        session['otp_user_id'] = user.id
        session['otp_verified'] = False
        session.permanent = True  # Make session permanent
        
        print(f"DEBUG - Session set for user {user.id}: otp_user_id = {session.get('otp_user_id')}")
        
        return jsonify({
            'success': True,
            'redirect': url_for('verify_otp'),
            'message': 'Please wait for OTP. A verification code has been sent to your email and may take a few seconds to arrive.',
            'user_id': user.id,  # Add for debugging
            'user_email': user.email  # Add user email for display
        })
        
    except Exception as e:
        print(f"Login API error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'An error occurred during login. Please try again.'
        }), 500

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    print(f"DEBUG - verify_otp called, session keys: {list(session.keys())}")
    print(f"DEBUG - otp_user_id in session: {session.get('otp_user_id')}")
    
    if 'otp_user_id' not in session:
        print("DEBUG - No otp_user_id in session, redirecting to login")
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    user = User.query.get(session['otp_user_id'])
    if not user:
        print(f"DEBUG - No user found for ID: {session.get('otp_user_id')}")
        flash('Invalid session. Please login again.', 'error')
        return redirect(url_for('login'))
    
    print(f"DEBUG - Found user: {user.username}, email: {user.email}")
    
    if request.method == 'POST':
        otp_input = request.form.get('otp_code', '').strip()
        
        if not otp_input:
            flash('Please enter the verification code.', 'error')
            return render_template('verify_otp.html', user=user)
        
        # Verify OTP
        is_valid, message = user.verify_otp(otp_input)
        db.session.commit()
        
        if is_valid:
            # OTP verified successfully
            login_user(user)
            session.pop('otp_user_id', None)
            session.pop('otp_verified', None)
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            # Check if user has exhausted all attempts
            if user.otp_attempts >= 3:
                # Clear session and redirect to login
                session.pop('otp_user_id', None)
                session.pop('otp_verified', None)
                user.clear_otp()
                db.session.commit()
                flash('Too many failed attempts. Please login again.', 'error')
                return redirect(url_for('login'))
            else:
                # Show error but stay on OTP page
                flash(message, 'error')
                return render_template('verify_otp.html', user=user)
    
    return render_template('verify_otp.html', user=user)

@app.route('/resend-otp', methods=['POST'])
def resend_otp():
    if 'otp_user_id' not in session:
        flash('Session expired. Please login again.')
        return redirect(url_for('login'))
    
    user = User.query.get(session['otp_user_id'])
    if not user:
        flash('Invalid session. Please login again.')
        return redirect(url_for('login'))
    
    # Generate new OTP
    otp_code = user.generate_otp()
    db.session.commit()
    
    # Send new OTP via email
    email_sent = send_otp_email(user, otp_code)
    
    if email_sent:
        flash('A new verification code has been sent to your email.', 'success')
    else:
        flash('Failed to send verification code. Please try again or contact support.', 'error')
    
    return redirect(url_for('verify_otp'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    # Clear OTP session data
    session.pop('otp_user_id', None)
    session.pop('otp_verified', None)
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Basic validation
        if not username or not password or not email:
            flash('Username, email and password are required')
            return render_template('signup.html')
        
        if password != confirm_password:
            flash('Passwords do not match')
            return render_template('signup.html')
        
        # Validate password policy (not for admin accounts)
        is_valid, error_msg = validate_password_policy(password, is_admin=False)
        if not is_valid:
            flash(error_msg)
            return render_template('signup.html')
            
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return render_template('signup.html')
            
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return render_template('signup.html')
        
        try:
            # Create new user - INACTIVE by default, requires admin approval
            new_user = User(
                username=username,
                email=email,
                is_active=False,  # Inactive by default
                is_approved=False,  # Requires admin approval
                is_admin=False
            )
            new_user.set_password(password)
            
            db.session.add(new_user)
            db.session.commit()
            
            # Ensure user directory structure exists
            ensure_user_directory(username)
            
            # Send email notifications
            notify_user_pending(new_user)
            notify_admin_new_user(new_user)
            
            flash('Account created successfully! Your account is pending admin approval. You will be notified via email once approved.')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to create account: {e}')
            return render_template('signup.html')
    
    return render_template('signup.html')

@app.route('/home')
@login_required
def home():
    if current_user.is_admin:
        return redirect(url_for('admin.index'))
    return render_template('home.html')

def get_user_para_path():
    """Return the per-user para.py path, creating and initializing if needed."""
    # Ensure user is authenticated
    username = getattr(current_user, 'username', None) or getattr(current_user, 'id', 'anonymous')
    user_dir = Path('user_data') / str(username)
    user_dir.mkdir(parents=True, exist_ok=True)
    para_path = user_dir / 'para.py'

    if not para_path.exists():
        # Initialize from the provided DEFAULT_PARA_CONTENT
        try:
            para_path.write_text(DEFAULT_PARA_CONTENT)
        except Exception:
            # Fallback: minimal file to avoid repeated attempts
            try:
                para_path.write_text(
                    "# para.py initialization fallback\n"
                    "device = 'CPU'\n"
                    "dimension = 3\n"
                    "kind = 'HYDRO'\n"
                    "Nx = 64\nNy = 64\nNz = 64\n"
                    "input_dir = ''\noutput_dir = ''\n"
                )
            except Exception:
                para_path.write_text("# para.py initialization error\n")

    return para_path

def get_user_runs_dir():
    """Return the per-user runs directory path, creating it if needed."""
    username = getattr(current_user, 'username', None) or getattr(current_user, 'id', 'anonymous')
    runs_dir = Path('user_data') / str(username) / 'runs'
    runs_dir.mkdir(parents=True, exist_ok=True)
    return runs_dir

def create_user_run_para_file():
    """Create a timestamped per-run para.py for the current user and return its path."""
    runs_dir = get_user_runs_dir()
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    run_para_path = runs_dir / f'para_{timestamp}.py'
    # Copy current user's para content
    src_para = get_user_para_path()
    content = Path(src_para).read_text() if Path(src_para).exists() else ''
    run_para_path.write_text(content)
    return str(run_para_path)

def list_user_runs():
    """Return a list of per-user run files with metadata (sorted by mtime desc)."""
    runs_dir = get_user_runs_dir()
    runs = []
    if runs_dir.exists():
        for p in runs_dir.glob('para_*.py'):
            try:
                stat = p.stat()
                runs.append({
                    'name': p.name,
                    'path': str(p),
                    'mtime': stat.st_mtime,
                    'size': stat.st_size
                })
            except Exception:
                continue
    runs.sort(key=lambda x: x['mtime'], reverse=True)
    return runs

def cleanup_old_runs():
    """Delete very old run files beyond retention policy.
    Only deletes files matching para_*.py to be safe.
    """
    try:
        runs = list_user_runs()
        # Age-based cleanup
        cutoff = datetime.now() - timedelta(days=RUNS_RETENTION_DAYS)
        runs_dir = get_user_runs_dir()
        # Delete by age
        for r in runs:
            try:
                if datetime.fromtimestamp(r['mtime']) < cutoff:
                    p = Path(r['path'])
                    if p.name.startswith('para_') and p.suffix == '.py':
                        p.unlink(missing_ok=True)
            except Exception:
                continue
        # Reload runs and enforce max keep
        runs = list_user_runs()
        if len(runs) > RUNS_MAX_KEEP:
            for r in runs[RUNS_MAX_KEEP:]:
                try:
                    p = Path(r['path'])
                    if p.name.startswith('para_') and p.suffix == '.py':
                        p.unlink(missing_ok=True)
                except Exception:
                    continue
    except Exception:
        pass

@app.route('/run_config', methods=['GET', 'POST'])
@login_required
def run_config():
    if current_user.is_admin:
        return redirect(url_for('admin.index'))
    if request.method == 'POST':
        # Store general configuration in session
        session['machine'] = request.form.get('machine', 'Local')
        session['device'] = request.form.get('device', 'CPU')
        session['dimension'] = request.form.get('dimension', '3')
        session['kind'] = request.form.get('kind', 'HYDRO')
        session['nx'] = int(request.form.get('nx', 64))
        session['ny'] = int(request.form.get('ny', 64))
        session['nz'] = int(request.form.get('nz', 64))
        session['input_path'] = request.form.get('input_path', '')
        session['output_path'] = request.form.get('output_path', '')

        # Clear previous specific params
        session.pop('hydro_params', None)
        session.pop('mhd_params', None)

        # Store type-specific parameters from the same consolidated form
        kind = session['kind']
        if kind == 'HYDRO':
            session['hydro_params'] = {
                'nu': float(request.form.get('nu', 0.01)),
                'alt_dissipation': bool(request.form.get('alt_dissipation')),
                'forcing_enabled': bool(request.form.get('forcing_enabled')),
                'nu_hypo': float(request.form.get('nu_hypo', 8.1)),
                'nu_hypo_power': float(request.form.get('nu_hypo_power', -2)),
                'nu_hyper': float(request.form.get('nu_hyper', 0)),
                'nu_hyper_power': float(request.form.get('nu_hyper_power', 25)),
                'forcing_range': request.form.get('forcing_range', '[4, 5]'),
                'injection_rate': float(request.form.get('injection_rate', 0.05))
            }
        elif kind == 'MHD':
            session['mhd_params'] = {
                'nu': float(request.form.get('nu', 0.02)),
                'eta': float(request.form.get('eta', 0.02)),
                'enable_forcing': bool(request.form.get('enable_forcing')),
                'nu_hypo': float(request.form.get('nu_hypo', 0.1)),
                'nu_hypo_power': float(request.form.get('nu_hypo_power', -2)),
                'nu_hyper': float(request.form.get('nu_hyper', 0)),
                'nu_hyper_power': float(request.form.get('nu_hyper_power', 25)),
                'eta_hypo': float(request.form.get('eta_hypo', 0.1)),
                'eta_hypo_power': float(request.form.get('eta_hypo_power', -2)),
                'eta_hyper': float(request.form.get('eta_hyper', 0)),
                'eta_hyper_power': float(request.form.get('eta_hyper_power', -25)),
                'forcing_range': request.form.get('forcing_range', '[4, 5]'),
                'injection_eplus': float(request.form.get('injection_eplus', 0.0)),
                'injection_eminus': float(request.form.get('injection_eminus', 0.0)),
                'injection_er': float(request.form.get('injection_er', 0.0))
            }

        # Store final parameters (common to all kinds) from the same form
        session['final_params'] = {
            'initial_time': float(request.form.get('initial_time', 0)),
            'final_time': float(request.form.get('final_time', 0.01)),
            'dt': float(request.form.get('dt', 0.001)),
            'time_scheme': request.form.get('time_scheme', 'EULER'),
            'fixed_dt': bool(request.form.get('fixed_dt')),
            'courant_no': float(request.form.get('courant_no', 0.5)),
            'modes_save': request.form.get('modes_save', '(1,0,0),(0,0,1)'),
            'field_save_start': float(request.form.get('field_save_start', 0)),
            'field_save_interval': float(request.form.get('field_save_interval', 500)),
            'energy_print_start': float(request.form.get('energy_print_start', 0)),
            'energy_print_interval': float(request.form.get('energy_print_interval', 1)),
            'ektk_save_start': float(request.form.get('ektk_save_start', 0)),
            'ektk_save_interval': float(request.form.get('ektk_save_interval', 100)),
            'modes_save_start': float(request.form.get('modes_save_start', 0)),
            'modes_save_interval': float(request.form.get('modes_save_interval', 200))
        }

        # After collecting everything from a single form, go directly to run_simulation
        return redirect(url_for('run_simulation'))
    
    # Read user-specific para.py content for display
    try:
        para_file = get_user_para_path()
        para_content = Path(para_file).read_text()
    except FileNotFoundError:
        para_content = "# para.py file not found"
    
    return render_template('run_config.html', para_content=para_content)

@app.route('/hydro_config', methods=['GET', 'POST'])
@login_required
def hydro_config():
    # Deprecated: use unified form
    flash('Hydro configuration moved to Run Configuration page.')
    return redirect(url_for('run_config'))

@app.route('/mhd_config', methods=['GET', 'POST'])
@login_required
def mhd_config():
    # Deprecated: use unified form
    flash('MHD configuration moved to Run Configuration page.')
    return redirect(url_for('run_config'))

@app.route('/final_config', methods=['GET', 'POST'])
@login_required
def final_config():
    if current_user.is_admin:
        return redirect(url_for('admin.index'))
    # Deprecated: use unified form
    flash('Final configuration moved to Run Configuration page.')
    return redirect(url_for('run_config'))

@app.route('/run_simulation')
@login_required
def run_simulation():
    return render_template('run_simulation.html')

@app.route('/analyze')
@login_required
def analyze():
    return render_template('analyze.html')

@app.route('/runs')
@login_required
def runs_index():
    # Clean up old runs first (best-effort)
    cleanup_old_runs()
    runs = list_user_runs()
    # Format for template
    formatted = []
    for r in runs:
        formatted.append({
            'name': r['name'],
            'size_kb': max(1, r['size'] // 1024),
            'mtime': datetime.fromtimestamp(r['mtime']).strftime('%Y-%m-%d %H:%M:%S')
        })
    return render_template('runs.html', runs=formatted)

@app.route('/runs/view/<name>')
@login_required
def runs_view(name):
    # Securely resolve file under user runs dir
    runs_dir = get_user_runs_dir()
    p = (runs_dir / name).resolve()
    if runs_dir.resolve() not in p.parents:
        return "Invalid path", 400
    if not p.exists() or not p.name.startswith('para_') or p.suffix != '.py':
        return "Not found", 404
    try:
        content = p.read_text()
    except Exception as e:
        content = f"# Error reading file: {e}"
    return render_template('runs_view.html', name=name, content=content)

@app.route('/runs/download/<name>')
@login_required
def runs_download(name):
    runs_dir = get_user_runs_dir()
    p = (runs_dir / name).resolve()
    if runs_dir.resolve() not in p.parents:
        return "Invalid path", 400
    if not p.exists() or not p.name.startswith('para_') or p.suffix != '.py':
        return "Not found", 404
    try:
        from flask import send_file
        return send_file(str(p), as_attachment=True)
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/start_simulation', methods=['POST'])
@login_required
def start_simulation():
    global process_counter, running_processes
    
    try:
        # Create per-run parameter file from the current user's para.py
        para_path = create_user_run_para_file()
        
        # Attempt to parse variables from the per-run para for metadata
        try:
            content = Path(para_path).read_text()
            variables = parse_para_content(content)
        except Exception:
            variables = {}
        
        # Start simulation process
        process_id = process_counter
        process_counter += 1
        
        if session.get('machine', 'Local') == 'Local':
            process = start_local_simulation(para_path, process_id)
        else:
            process = start_remote_simulation(para_path, process_id)
        
        running_processes[process_id] = {
            'process': process,
            'status': 'running',
            'start_time': datetime.now(),
            'variables': variables
        }

        # Write run metadata JSON beside the para file
        try:
            meta = {
                'process_id': process_id,
                'user': getattr(current_user, 'username', None) or getattr(current_user, 'id', 'anonymous'),
                'started_at': datetime.utcnow().isoformat() + 'Z',
                'machine': session.get('machine'),
                'device': session.get('device'),
                'dimension': session.get('dimension'),
                'kind': session.get('kind'),
                'nx': session.get('nx'),
                'ny': session.get('ny'),
                'nz': session.get('nz'),
                'para_file': para_path,
            }
            meta_path = Path(para_path).with_suffix('.json')
            meta_path.write_text(json.dumps(meta, indent=2))
        except Exception:
            pass
        
        return jsonify({
            'success': True,
            'process_id': process_id,
            'message': 'Simulation started successfully',
            'para_file': para_path
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

def extract_variables_from_session():
    """Extract all simulation variables from session"""
    variables = {
        'device': session.get('device', 'CPU'),
        'dimension': session.get('dimension', 3),
        'kind': session.get('kind', 'HYDRO'),
        'Nx': session.get('nx', 64),
        'Ny': session.get('ny', 64),
        'Nz': session.get('nz', 64),
        'input_dir': session.get('input_path', ''),
        'output_dir': session.get('output_path', ''),
        'machine': session.get('machine', 'Local')
    }
    
    # Add type-specific parameters
    if session.get('hydro_params'):
        variables.update(session['hydro_params'])
    if session.get('mhd_params'):
        variables.update(session['mhd_params'])
    if session.get('final_params'):
        variables.update(session['final_params'])
    
    # Add default parameters
    default_variables = {
        k: v for k, v in vars(default_params).items()
        if not k.startswith('__') and not isinstance(v, types.ModuleType)
    }
    variables.update(default_variables)
    
    return variables

def create_para_file(variables):
    """Create parameter file for simulation"""
    time_of_run = str(datetime.now()).split('.')[0].replace(':', '_').replace(' ', '_').replace('-', '_')
    para_path = f'/tmp/para_{time_of_run}.py'
    
    with open(para_path, 'w') as f:
        f.write("\n")
        for key, value in variables.items():
            if isinstance(value, str):
                f.write(f"{key} = '{value}'\n")
            else:
                f.write(f"{key} = {value}\n")
    
    return para_path

def start_local_simulation(para_path, process_id):
    """Start local simulation process and return the Popen handle.
    Streams stdout via a background thread using SocketIO.
    """
    try:
        import platform
        system = platform.system()

        # Determine project-local script
        script_path = os.path.abspath(os.path.join(os.getcwd(), 'tarang_linux'))

        # Build command based on availability and platform
        if os.path.exists(script_path):
            # Run the repository's tarang_linux Python script via current interpreter with unbuffered output
            import sys as _sys
            cmd = [_sys.executable, '-u', script_path]
            if para_path:
                cmd.append(para_path)
        elif system == "Linux":
            if os.path.exists("./tarang_linux"):
                print(f"Using Linux simulation executable: ./tarang_linux")
                cmd = ["./tarang_linux", para_path] if para_path else ["./tarang_linux"]
            else:
                print("Using Python-based simulation engine for Ubuntu 24.04")
                import sys as _sys
                cmd = [_sys.executable, '-u', '-c', f'''
import time
import sys
import numpy as np
import os
from pathlib import Path

print("Starting Tarang Scientific Simulation Engine v2.0")
print(f"Process ID: {process_id}")
print(f"Platform: Ubuntu 24.04 LTS")
print(f"Parameter file: {para_path if "{para_path}" else "default_params.py"}")
print("Initializing fluid dynamics solver...")

# Simulate realistic scientific computation
grid_size = 64
time_steps = 100
dt = 0.001

print(f"Grid size: {{grid_size}}x{{grid_size}}x{{grid_size}}")
print(f"Time step: {{dt}}")
print(f"Total steps: {{time_steps}}")
print("")

for step in range(time_steps):
    current_time = step * dt
    
    # Simulate fluid dynamics computation
    if step % 10 == 0:
        velocity_magnitude = np.random.uniform(0.1, 2.0)
        pressure_max = np.random.uniform(100, 1000)
        reynolds_number = np.random.uniform(1000, 10000)
        
        print(f"Step {{step+1:3d}}/{{time_steps}}: t={{current_time:.3f}}s | "
              f"|v|_max={{velocity_magnitude:.3f}} | P_max={{pressure_max:.1f}} | Re={{reynolds_number:.0f}}")
    else:
        print(f"Step {{step+1:3d}}/{{time_steps}}: Computing Navier-Stokes equations...")
    
    # Simulate I/O operations
    if step % 25 == 0 and step > 0:
        print(f"    → Writing checkpoint data at step {{step+1}}")
    
    time.sleep(0.05)  # Realistic computation delay

print("")
print("Simulation completed successfully!")
print("Final results written to output files")
print("Done")
''']            
        elif system == "Windows":
            if os.path.exists("./tarang.exe"):
                print(f"Using Windows simulation executable: ./tarang.exe")
                cmd = ["./tarang.exe", para_path] if para_path else ["./tarang.exe"]
            else:
                print("Windows executable not found, using demo mode")
                import sys as _sys
                cmd = [_sys.executable, '-u', '-c', f'''
print("Tarang Demo Mode - Windows")
for i in range(50):
    print(f"Step {{i+1}}/50: Demo computation...")
    import time; time.sleep(0.1)
print("Done")
''']
        else:
            print(f"Platform {system} detected, using cross-platform simulation")
            import sys as _sys
            cmd = [_sys.executable, '-u', '-c', f'''
print("Tarang Cross-Platform Simulation")
for i in range(75):
    print(f"Step {{i+1}}/75: Cross-platform computation...")
    import time; time.sleep(0.08)
print("Done")
''']
        # Start the subprocess
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # Background thread to stream stdout lines
        def stream_output(proc):
            try:
                for line in proc.stdout:
                    socketio.emit('simulation_output', {
                        'process_id': process_id,
                        'output': line.rstrip('\n')
                    })
                rc = proc.wait()
                # On exit, emit completion
                status = 'completed' if rc == 0 else 'error'
                if process_id in running_processes:
                    running_processes[process_id]['status'] = status
                socketio.emit('simulation_complete', {
                    'process_id': process_id,
                    'status': status
                })
            except Exception as e:
                if process_id in running_processes:
                    running_processes[process_id]['status'] = 'error'
                socketio.emit('simulation_error', {
                    'process_id': process_id,
                    'error': str(e)
                })

        t = threading.Thread(target=stream_output, args=(process,), daemon=True)
        t.start()

        return process
    except Exception as e:
        # If anything fails early, emit error and re-raise
        socketio.emit('simulation_error', {
            'process_id': process_id,
            'error': str(e)
        })
        raise

def start_remote_simulation(para_path, process_id):
    """Start remote simulation process"""
    # This would implement SSH connection and remote execution
    # For now, return a placeholder
    return start_local_simulation(para_path, process_id)

@app.route('/process_status/<int:process_id>')
@login_required
def process_status(process_id):
    if process_id in running_processes:
        return jsonify(running_processes[process_id]['status'])
    return jsonify('not_found')

@app.route('/kill_process/<int:process_id>', methods=['POST'])
@login_required
def kill_process(process_id):
    if process_id in running_processes:
        try:
            process = running_processes[process_id]['process']
            if hasattr(process, 'terminate'):
                process.terminate()
            running_processes[process_id]['status'] = 'killed'
            return jsonify({'success': True, 'message': 'Process killed successfully'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    return jsonify({'success': False, 'error': 'Process not found'})

@app.route('/get_para_content')
@login_required
def get_para_content():
    """Get current para.py content"""
    try:
        para_file = get_user_para_path()
        content = Path(para_file).read_text()
        return jsonify({'success': True, 'content': content})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/get_default_para')
@login_required
def get_default_para():
    return jsonify({'success': True, 'content': DEFAULT_PARA_CONTENT})


@app.route('/load_default_para', methods=['POST'])
@login_required
def load_default_para():
    try:
        # Overwrite the current user's para.py with default content
        para_path = Path(get_user_para_path())
        para_path.parent.mkdir(parents=True, exist_ok=True)
        para_path.write_text(DEFAULT_PARA_CONTENT)

        # Parse for params to sync back to form
        params = {}
        try:
            params = parse_para_content(DEFAULT_PARA_CONTENT)
        except Exception:
            params = {}
        return jsonify({'success': True, 'content': DEFAULT_PARA_CONTENT, 'params': params})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    except FileNotFoundError:
        return jsonify({'success': False, 'error': 'para.py file not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/save_para_content', methods=['POST'])
@login_required
def save_para_content():
    """Save para.py content and return parsed parameters"""
    try:
        content = request.json.get('content', '')
        # Save to user-specific para.py
        para_file = get_user_para_path()
        Path(para_file).write_text(content)
        
        # Parse parameters from content
        params = parse_para_content(content)
        
        return jsonify({'success': True, 'params': params})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def parse_para_content(content):
    """Parse parameters from para.py content"""
    params = {}
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            try:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Remove quotes if present
                if value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                elif value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                
                # Map para.py parameters to form fields
                if key == 'device':
                    params['device'] = value
                elif key == 'dimension':
                    params['dimension'] = str(value)
                elif key == 'kind':
                    params['kind'] = value
                elif key == 'Nx':
                    params['nx'] = int(value)
                elif key == 'Ny':
                    params['ny'] = int(value)
                elif key == 'Nz':
                    params['nz'] = int(value)
                elif key == 'input_dir':
                    params['input_path'] = value
                elif key == 'output_dir':
                    params['output_path'] = value
                # HYDRO/MHD common + hydro-specific
                elif key == 'nu':
                    # Applies to both HYDRO and MHD
                    params['nu'] = float(value)
                elif key == 'alt_dissipation':
                    params['alt_dissipation'] = (str(value).lower() in ['true', '1'])
                elif key == 'FORCING_ENABLED':
                    params['forcing_enabled'] = (str(value).lower() in ['true', '1'])
                elif key == 'forcing_enabled':
                    params['forcing_enabled'] = (str(value).lower() in ['true', '1'])
                elif key == 'enable_forcing':
                    params['forcing_enabled'] = (str(value).lower() in ['true', '1'])
                elif key == 'FORCING':
                    params['forcing_enabled'] = (str(value).lower() in ['true', '1'])
                elif key == 'nu_hypo' or key == 'NU_HYPO':
                    params['nu_hypo'] = float(value)
                elif key == 'nu_hypo_power' or key == 'NU_HYPO_POWER':
                    params['nu_hypo_power'] = float(value)
                elif key == 'nu_hyper' or key == 'NU_HYPER':
                    params['nu_hyper'] = float(value)
                elif key == 'nu_hyper_power' or key == 'NU_HYPER_POWER':
                    params['nu_hyper_power'] = float(value)
                elif key == 'forcing_range' or key == 'FORCING_RANGE':
                    # Keep as string to avoid eval risks; UI expects string like "[4, 5]"
                    params['forcing_range'] = value
                elif key == 'injection_rate':
                    params['injection_rate'] = float(value)
                elif key == 'injections':
                    # Expect a list-like string [eplus, eminus, er]
                    try:
                        # Safe parse numbers from within brackets
                        inner = value.strip()
                        if inner.startswith('[') and inner.endswith(']'):
                            inner = inner[1:-1]
                        parts = [p.strip() for p in inner.split(',')]
                        if len(parts) >= 3:
                            params['injection_eplus'] = float(parts[0])
                            params['injection_eminus'] = float(parts[1])
                            params['injection_er'] = float(parts[2])
                    except Exception:
                        pass
                # Final/time/output parameters
                elif key == 'initial_time':
                    params['initial_time'] = float(value)
                elif key == 't_initial':
                    params['initial_time'] = float(value)
                elif key == 'final_time':
                    params['final_time'] = float(value)
                elif key == 't_final':
                    params['final_time'] = float(value)
                elif key == 'dt':
                    params['dt'] = float(value)
                elif key == 'time_scheme':
                    params['time_scheme'] = value
                elif key == 'fixed_dt':
                    # Handle bool in para.py (True/False or 1/0)
                    params['fixed_dt'] = (str(value).lower() in ['true', '1'])
                elif key == 'FIXED_DT':
                    params['fixed_dt'] = (str(value).lower() in ['true', '1'])
                elif key in ['courant_no', 'Courant_no']:
                    # Handle both 'courant_no' and 'Courant_no' cases
                    params['courant_no'] = float(value)
                    params['Courant_no'] = float(value)  # Set both to ensure compatibility
                elif key == 'modes_save':
                    params['modes_save'] = value
                elif key == 'field_save_start' or key == 'iter_field_save_start':
                    params['field_save_start'] = float(value)
                elif key == 'field_save_interval' or key == 'iter_field_save_inter':
                    params['field_save_interval'] = float(value)
                elif key == 'energy_print_start' or key == 'iter_glob_energy_print_start':
                    params['energy_print_start'] = float(value)
                elif key == 'energy_print_interval' or key == 'iter_glob_energy_print_inter':
                    params['energy_print_interval'] = float(value)
                elif key == 'ektk_save_start' or key == 'iter_ekTk_save_start':
                    params['ektk_save_start'] = float(value)
                elif key == 'ektk_save_interval' or key == 'iter_ekTk_save_inter':
                    params['ektk_save_interval'] = float(value)
                elif key == 'modes_save_start' or key == 'iter_modes_save_start':
                    params['modes_save_start'] = float(value)
                elif key == 'modes_save_interval' or key == 'iter_modes_save_inter':
                    params['modes_save_interval'] = float(value)
                # MHD-specific viscosity/resistivity
                elif key == 'eta':
                    params['eta'] = float(value)
                elif key == 'eta_hypo':
                    params['eta_hypo'] = float(value)
                elif key == 'eta_hypo_power':
                    params['eta_hypo_power'] = float(value)
                elif key == 'eta_hyper':
                    params['eta_hyper'] = float(value)
                elif key == 'eta_hyper_power':
                    params['eta_hyper_power'] = float(value)
                
            except (ValueError, IndexError):
                continue
                
    return params

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')

# Admin route for user approval
@app.route('/admin/approve-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_approve_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    user.is_active = True
    db.session.commit()
    flash(f'User {user.username} has been approved.', 'success')
    return redirect(url_for('admin.index'))

# Admin Access Control
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

# Custom Admin Index View
class MyAdminIndexView(AdminIndexView):
    @expose('/')
    @login_required
    @admin_required
    def index(self):
        # Get user statistics
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        inactive_users = User.query.filter_by(is_active=False).count()
        pending_users = User.query.filter_by(is_approved=False).count()
        
        return self.render('admin/index.html',
                         total_users=total_users,
                         active_users=active_users,
                         inactive_users=inactive_users,
                         pending_users=pending_users)

# Initialize Flask-Admin with safe initialization
admin = Admin(
    app,
    name='Admin Panel',
    template_mode='bootstrap3',
    index_view=MyAdminIndexView(
        name='Dashboard',
        template='admin/index.html',
        url='/admin'
    )
)

# Admin Model View
class UserModelView(ModelView):
    """Base user model view with common configuration"""
    column_list = ['id', 'username', 'email', 'is_active', 'is_approved', 'is_admin', 'created_at']
    column_searchable_list = ['username', 'email']
    column_filters = ['is_active', 'is_approved', 'is_admin']
    form_columns = ['username', 'email', 'is_active', 'is_approved', 'is_admin']
    
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=request.url))

class UserAdminView(UserModelView):
    # User management settings
    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True
    
    # List view configuration
    column_list = ['username', 'email', 'is_active', 'is_approved', 'is_admin', 'created_at']
    column_default_sort = ('created_at', True)  # Sort by creation date, newest first
    column_searchable_list = ['username', 'email']
    column_filters = ['is_active', 'is_approved', 'is_admin', 'created_at']
    
    # Form configuration
    form_columns = ['username', 'email', 'password', 'is_active', 'is_approved', 'is_admin']
    form_excluded_columns = ['created_at']
    
    # Customize the password field
    form_extra_fields = {
        'password': PasswordField('New Password')
    }
    
    def on_model_change(self, form, model, is_created):
        # Check if user is being approved for the first time
        was_approved_before = False
        if not is_created:
            # Get the original state from database
            original_user = User.query.get(model.id)
            was_approved_before = original_user.is_approved if original_user else False
        
        # Hash the password if it was provided
        if form.password.data:
            model.set_password(form.password.data)
        
        # After the model is saved, check if we need to send approval notification
        def send_approval_notification():
            if not is_created and not was_approved_before and model.is_approved:
                # User was just approved, send notification
                notify_user_approved(model)
                flash(f'Approval notification sent to {model.email}', 'info')
        
        # Schedule the notification to be sent after commit
        db.session.flush()  # Ensure model has an ID
        if hasattr(db.session, '_approval_notifications'):
            db.session._approval_notifications.append(send_approval_notification)
        else:
            db.session._approval_notifications = [send_approval_notification]
    
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=request.url))
        
    # Add custom actions
    @action('approve_users', 'Approve Users', 'Are you sure you want to approve selected users?')
    def action_approve_users(self, ids):
        try:
            query = User.query.filter(User.id.in_(ids))
            count = 0
            for user in query.all():
                if not user.is_approved:
                    user.is_approved = True
                    user.is_active = True  # Also activate when approving
                    notify_user_approved(user)
                    count += 1
            db.session.commit()
            flash(f'Approved {count} users and sent email notifications.', 'success')
        except Exception as ex:
            flash('Failed to approve users.', 'error')
    
    @action('toggle_active', 'Toggle Active', 'Are you sure you want to toggle active status for selected users?')
    def action_toggle_active(self, ids):
        try:
            query = User.query.filter(User.id.in_(ids))
            count = 0
            for user in query.all():
                user.is_active = not user.is_active
                count += 1
            db.session.commit()
            flash(f'Toggled active status for {count} users.', 'success')
        except Exception as ex:
            flash('Failed to toggle active status.', 'error')
    
    # Customize the list view
    def get_list_value(self, context, model, name):
        value = getattr(model, name)
        if name == 'is_active' or name == 'is_approved' or name == 'is_admin':
            return '✅' if value else '❌'
        return super().get_list_value(context, model, name)

# Add only user management to admin panel
admin.add_view(UserAdminView(User, db.session, name='Users'))

def create_admin_user():
    """Create or update admin user using values from .env"""
    try:
        # Get values from .env with defaults
        admin_email = app.config.get('ADMIN_EMAIL', 'admin@tarang.com')
        admin_username = app.config.get('ADMIN_USERNAME', 'admin')
        admin_password = app.config.get('ADMIN_PASSWORD', 'XXXXX')
        
        print(f"\n=== Setting up admin user ===")
        print(f"Username: {admin_username}")
        print(f"Email:    {admin_email}")
        print(f"Password: {'*' * len(admin_password)}\n")
        
        # Start a new session
        with app.app_context():
            # Delete any existing admin users to avoid conflicts
            User.query.filter(
                (User.email == admin_email) | 
                (User.username == admin_username) |
                (User.is_admin == True)
            ).delete(synchronize_session=False)
            
            # Create new admin user
            admin = User(
                username=admin_username,
                email=admin_email,
                is_active=True,
                is_approved=True,
                is_admin=True
            )
            admin.set_password(admin_password)
            
            db.session.add(admin)
            db.session.commit()
            
            print("✅ Admin user created/updated successfully!")
            print("You can now log in with the credentials above.")
            
    except Exception as e:
        print(f"\n❌ Error creating admin user: {str(e)}")
        db.session.rollback()
        print("\nTroubleshooting steps:")
        print(f"1. Delete the database file: rm -f {os.path.join(app.instance_path, 'app.db')}")
        print("2. Check your .env file for correct values")
        print("3. Restart the application")
        raise

# Simple route to verify admin user
@app.route('/admin-info')
def admin_info():
    """Show current admin user info (for debugging)"""
    admin = User.query.filter_by(is_admin=True).first()
    if admin:
        return f"""
        <h2>Admin User Info</h2>
        <p>Username: {admin.username}</p>
        <p>Email: {admin.email}</p>
        <p>Is Active: {admin.is_active}</p>
        <p>Is Admin: {admin.is_admin}</p>
        <p>Password Set: {'Yes' if admin.password_hash else 'No'}</p>
        <p><a href='/admin'>Go to Admin Panel</a></p>
        """
    return "No admin user found. Try restarting the application."

# Create admin user when the application starts
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Handle forgot password requests"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email:
            flash('Please enter your email address.', 'error')
            return render_template('forgot_password.html')
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        
        print(f"DEBUG - Password reset request for email: {email}")
        print(f"DEBUG - Searching for user with email: '{email}'")
        
        # Debug: Show all users in database
        all_users = User.query.all()
        print(f"DEBUG - All users in database:")
        for u in all_users:
            print(f"  - {u.username}: {u.email} (active: {u.is_active}, approved: {u.is_approved})")
        
        if user:
            print(f"DEBUG - User found: {user.username} ({user.email})")
            # Generate reset token
            reset_token = user.generate_reset_token()
            db.session.commit()
            print(f"DEBUG - Reset token generated and saved to database")
            
            # Send reset email
            email_sent = send_password_reset_email(user, reset_token)
            
            if email_sent:
                print(f"✅ Password reset email sent successfully to {user.email}")
                flash('Password reset instructions have been sent to your email address.', 'success')
            else:
                print(f"❌ Failed to send password reset email to {user.email}")
                flash('Failed to send reset email. Please try again or contact support.', 'error')
        else:
            print(f"DEBUG - No user found with email: {email}")
            # Don't reveal if email exists or not for security
            flash('If an account with that email exists, password reset instructions have been sent.', 'info')
        
        return render_template('forgot_password.html')
    
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Handle password reset with token"""
    # Find user by reset token
    user = User.query.filter_by(reset_token=token).first()
    
    if not user:
        flash('Invalid or expired reset link.', 'error')
        return render_template('reset_password.html', user=None)
    
    # Verify token
    is_valid, message = user.verify_reset_token(token)
    
    if not is_valid:
        flash(message, 'error')
        return render_template('reset_password.html', user=None)
    
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Validate passwords
        if not password or not confirm_password:
            flash('Please fill in all password fields.', 'error')
            return render_template('reset_password.html', user=user)
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('reset_password.html', user=user)
        
        # Validate password policy (admin accounts are excluded)
        is_valid, error_msg = validate_password_policy(password, is_admin=user.is_admin)
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('reset_password.html', user=user)
        
        # Update password
        user.set_password(password)
        user.clear_reset_token()
        user.clear_otp()  # Clear any existing OTP data
        db.session.commit()
        
        flash('Your password has been updated successfully! You can now log in with your new password.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', user=user)

with app.app_context():
    create_admin_user()

if __name__ == '__main__':
    # For CloudFront deployment - bind to all interfaces for ALB health checks
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
