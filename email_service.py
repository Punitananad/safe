# Email Service with Dual Configuration
import os
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from flask_mail import Mail, Message
from flask import current_app

class EmailService:
    def __init__(self, app=None):
        self.app = app
        self.admin_mail = None
        self.user_mail = None
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize dual email configuration"""
        self.app = app
        
        # Admin email configuration (for sending to admin)
        admin_config = {
            'MAIL_SERVER': 'smtp.gmail.com',
            'MAIL_PORT': 587,
            'MAIL_USE_TLS': True,
            'MAIL_USERNAME': os.environ.get('MAIL_USERNAME'),  # punitanand146@gmail.com
            'MAIL_PASSWORD': os.environ.get('MAIL_PASSWORD'),  # jimbaarhqpdrtopx
            'MAIL_DEFAULT_SENDER': (
                os.environ.get('MAIL_SENDER_NAME', 'CalculatenTrade Support'),
                os.environ.get('MAIL_USERNAME')
            )
        }
        
        # User email configuration (for sending to users)
        user_config = {
            'MAIL_SERVER': 'smtp.gmail.com',
            'MAIL_PORT': 587,
            'MAIL_USE_TLS': True,
            'MAIL_USERNAME': 'calculatentrade@gmail.com',
            'MAIL_PASSWORD': 'bccpjnvzbbsqmkcf',
            'MAIL_DEFAULT_SENDER': (
                'CalculatenTrade Alerts',
                'calculatentrade@gmail.com'
            )
        }
        
        # Create separate Mail instances
        self.admin_mail = Mail()
        self.user_mail = Mail()
        
        # Configure admin mail
        for key, value in admin_config.items():
            app.config[f'ADMIN_{key}'] = value
        
        # Configure user mail  
        for key, value in user_config.items():
            app.config[f'USER_{key}'] = value
    
    def send_admin_email(self, to, subject, html, body=None):
        """Send email to admin using admin configuration"""
        try:
            with self.app.app_context():
                # Temporarily set admin config
                original_config = {}
                admin_keys = ['MAIL_SERVER', 'MAIL_PORT', 'MAIL_USE_TLS', 'MAIL_USERNAME', 'MAIL_PASSWORD', 'MAIL_DEFAULT_SENDER']
                
                for key in admin_keys:
                    original_config[key] = self.app.config.get(key)
                    self.app.config[key] = self.app.config.get(f'ADMIN_{key}')
                
                # Send email
                msg = Message(subject=subject, recipients=[to], html=html, body=body)
                self.admin_mail.send(msg)
                
                # Restore original config
                for key, value in original_config.items():
                    if value is not None:
                        self.app.config[key] = value
                    else:
                        self.app.config.pop(key, None)
                        
                print(f"[ADMIN EMAIL] Successfully sent to: {to}")
                
        except Exception as e:
            print(f"[ADMIN EMAIL] Failed to send to {to}: {str(e)}")
            raise
    
    def send_user_email(self, to, subject, html, body=None):
        """Send email to users using user configuration"""
        try:
            with self.app.app_context():
                # Temporarily set user config
                original_config = {}
                user_keys = ['MAIL_SERVER', 'MAIL_PORT', 'MAIL_USE_TLS', 'MAIL_USERNAME', 'MAIL_PASSWORD', 'MAIL_DEFAULT_SENDER']
                
                for key in user_keys:
                    original_config[key] = self.app.config.get(key)
                    self.app.config[key] = self.app.config.get(f'USER_{key}')
                
                # Send email
                msg = Message(subject=subject, recipients=[to], html=html, body=body)
                self.user_mail.send(msg)
                
                # Restore original config
                for key, value in original_config.items():
                    if value is not None:
                        self.app.config[key] = value
                    else:
                        self.app.config.pop(key, None)
                        
                print(f"[USER EMAIL] Successfully sent to: {to}")
                
        except Exception as e:
            print(f"[USER EMAIL] Failed to send to {to}: {str(e)}")
            raise

# Global email service instance
email_service = EmailService()

def generate_otp():
    """Generate 6-digit OTP"""
    return f"{secrets.randbelow(1_000_000):06d}"

def hash_otp(otp, salt):
    """Hash OTP with salt"""
    return hashlib.sha256(salt + otp.encode()).hexdigest()

def verify_otp_hash(otp, salt_hex, stored_hash):
    """Verify OTP against stored hash"""
    salt = bytes.fromhex(salt_hex)
    calculated_hash = hashlib.sha256(salt + otp.encode()).hexdigest()
    return calculated_hash == stored_hash