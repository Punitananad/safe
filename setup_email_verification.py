#!/usr/bin/env python3
"""
Setup script for email verification system
Run this script to initialize the database and test email functionality
"""

import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, upgrade
from email_service import EmailService, email_service

def setup_database():
    """Initialize database with email verification tables"""
    print("Setting up database...")
    
    # Import app to get database configuration
    from app import app, db
    
    with app.app_context():
        try:
            # Run migrations
            upgrade()
            print("[OK] Database migrations completed successfully!")
            
            # Verify tables exist
            from sqlalchemy import text
            
            tables_to_check = [
                'users',
                'reset_otp', 
                'email_verify_otp',
                'delete_account_otp',
                'user_settings'
            ]
            
            for table in tables_to_check:
                result = db.session.execute(
                    text(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')")
                ).fetchone()
                
                if result[0]:
                    print(f"[OK] Table '{table}' exists")
                else:
                    print(f"[ERROR] Table '{table}' missing")
            
            print("Database setup completed!")
            
        except Exception as e:
            print(f"[ERROR] Database setup failed: {e}")
            return False
    
    return True

def test_email_configuration():
    """Test both email configurations"""
    print("\nTesting email configurations...")
    
    # Check environment variables
    admin_email = os.environ.get('MAIL_USERNAME')
    admin_password = os.environ.get('MAIL_PASSWORD')
    
    print(f"Admin email configured: {admin_email}")
    print(f"Admin password configured: {'Yes' if admin_password else 'No'}")
    
    # Test user email configuration
    user_email = 'calculatentrade@gmail.com'
    user_password = 'bccpjnvzbbsqmkcf'
    
    print(f"User email configured: {user_email}")
    print(f"User password configured: {'Yes' if user_password else 'No'}")
    
    return True

def create_test_user():
    """Create a test user for verification"""
    from app import app, db, User
    
    with app.app_context():
        try:
            # Check if test user exists
            test_email = "test@example.com"
            existing_user = User.query.filter_by(email=test_email).first()
            
            if existing_user:
                print(f"Test user {test_email} already exists")
                return True
            
            # Create test user
            test_user = User(
                email=test_email,
                verified=False
            )
            test_user.set_password("TestPassword123!")
            
            db.session.add(test_user)
            db.session.commit()
            
            print(f"[OK] Test user created: {test_email}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to create test user: {e}")
            db.session.rollback()
            return False

def main():
    """Main setup function"""
    print("Setting up Email Verification System for CalculatenTrade")
    print("=" * 60)
    
    # Step 1: Setup database
    if not setup_database():
        print("[ERROR] Database setup failed. Exiting.")
        sys.exit(1)
    
    # Step 2: Test email configuration
    if not test_email_configuration():
        print("[ERROR] Email configuration test failed. Exiting.")
        sys.exit(1)
    
    # Step 3: Create test user
    if not create_test_user():
        print("[ERROR] Test user creation failed. Exiting.")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("[OK] Email verification system setup completed successfully!")
    print("\nNext steps:")
    print("1. Start your Flask application: python app.py")
    print("2. Register a new user to test email verification")
    print("3. Check your email for verification codes")
    print("4. Test forgot password functionality")
    print("\nEmail Configuration Summary:")
    print("- Admin emails (to punitanand146@gmail.com): For admin notifications")
    print("- User emails (from calculatentrade@gmail.com): For user verification & password recovery")

if __name__ == "__main__":
    main()