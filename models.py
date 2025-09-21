from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import bcrypt

# Initialize SQLAlchemy
db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_active = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # OTP fields for multi-factor authentication
    otp_code = db.Column(db.String(6))  # 6-digit OTP
    otp_expires_at = db.Column(db.DateTime)
    otp_attempts = db.Column(db.Integer, default=0)
    is_otp_verified = db.Column(db.Boolean, default=False)
    
    # Password reset fields
    reset_token = db.Column(db.String(100))  # Password reset token
    reset_token_expires_at = db.Column(db.DateTime)
    reset_attempts = db.Column(db.Integer, default=0)

    def set_password(self, password):
        # Ensure consistent bcrypt hashing
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), 
            bcrypt.gensalt(12)  # Use 12 rounds for good security
        ).decode('utf-8')
        print(f"DEBUG - Set password hash: {self.password_hash}")

    def check_password(self, password):
        if not self.password_hash:
            print("DEBUG - No password hash set")
            return False
            
        try:
            # Try bcrypt first
            is_valid = bcrypt.checkpw(
                password.encode('utf-8'), 
                self.password_hash.encode('utf-8')
            )
            print(f"DEBUG - Password check result: {is_valid}")
            return is_valid
        except Exception as e:
            print(f"DEBUG - Error checking password: {str(e)}")
            return False
    
    def generate_otp(self):
        """Generate a 6-digit OTP and set expiration time"""
        import random
        self.otp_code = f"{random.randint(100000, 999999)}"
        self.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)  # 10 minutes expiry
        self.otp_attempts = 0
        self.is_otp_verified = False
        print(f"DEBUG - Generated OTP: {self.otp_code} for user {self.username}")
        return self.otp_code
    
    def verify_otp(self, otp_input):
        """Verify the provided OTP"""
        if not self.otp_code or not self.otp_expires_at:
            return False, "No OTP generated"
        
        if datetime.utcnow() > self.otp_expires_at:
            return False, "OTP has expired"
        
        if self.otp_attempts >= 3:
            return False, "Too many failed attempts"
        
        if self.otp_code == otp_input:
            self.is_otp_verified = True
            self.otp_code = None  # Clear OTP after successful verification
            self.otp_expires_at = None
            self.otp_attempts = 0
            return True, "OTP verified successfully"
        else:
            self.otp_attempts += 1
            return False, f"Invalid OTP. {3 - self.otp_attempts} attempts remaining"
    
    def clear_otp(self):
        """Clear OTP data"""
        self.otp_code = None
        self.otp_expires_at = None
        self.otp_attempts = 0
        self.is_otp_verified = False
    
    def generate_reset_token(self):
        """Generate a secure password reset token"""
        import secrets
        import string
        
        # Generate a secure random token
        alphabet = string.ascii_letters + string.digits
        self.reset_token = ''.join(secrets.choice(alphabet) for _ in range(64))
        self.reset_token_expires_at = datetime.utcnow() + timedelta(hours=24)  # 24 hours expiry
        self.reset_attempts = 0
        print(f"DEBUG - Generated reset token for user {self.username}: {self.reset_token[:10]}...")
        return self.reset_token
    
    def verify_reset_token(self, token):
        """Verify the password reset token"""
        if not self.reset_token or not self.reset_token_expires_at:
            return False, "No reset token generated"
        
        if datetime.utcnow() > self.reset_token_expires_at:
            return False, "Reset token has expired"
        
        if self.reset_attempts >= 3:
            return False, "Too many failed reset attempts"
        
        if self.reset_token == token:
            return True, "Token verified successfully"
        else:
            self.reset_attempts += 1
            return False, f"Invalid reset token. {3 - self.reset_attempts} attempts remaining"
    
    def clear_reset_token(self):
        """Clear password reset data"""
        self.reset_token = None
        self.reset_token_expires_at = None
        self.reset_attempts = 0
