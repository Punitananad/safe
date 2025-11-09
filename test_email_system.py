#!/usr/bin/env python3
"""
Test script for email verification system
Run this to test email functionality without starting the full app
"""

import os
import sys
from datetime import datetime, timezone, timedelta

def test_email_service():
    """Test the email service functionality"""
    print("Testing Email Service...")
    
    try:
        from app import app
        from email_service import email_service
        
        with app.app_context():
            # Test user email
            print("Testing user email service...")
            email_service.send_user_email(
                to="test@example.com",  # Replace with your test email
                subject="Test Email - User Service",
                html="""
                <div style="font-family: Arial, sans-serif; padding: 20px;">
                    <h2 style="color: #27ae60;">[OK] User Email Service Test</h2>
                    <p>This is a test email from the user email service (calculatentrade@gmail.com).</p>
                    <p>If you receive this, the user email configuration is working correctly!</p>
                    <p><strong>Time:</strong> {}</p>
                </div>
                """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            print("[OK] User email test sent successfully!")
            
            # Test admin email
            print("Testing admin email service...")
            email_service.send_admin_email(
                to="punitanand146@gmail.com",
                subject="Test Email - Admin Service", 
                html="""
                <div style="font-family: Arial, sans-serif; padding: 20px;">
                    <h2 style="color: #3498db;">[OK] Admin Email Service Test</h2>
                    <p>This is a test email from the admin email service (punitanand146@gmail.com).</p>
                    <p>If you receive this, the admin email configuration is working correctly!</p>
                    <p><strong>Time:</strong> {}</p>
                </div>
                """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            print("[OK] Admin email test sent successfully!")
            
        return True
        
    except Exception as e:
        print(f"[ERROR] Email service test failed: {e}")
        return False

def test_otp_functions():
    """Test OTP generation and verification"""
    print("\nTesting OTP Functions...")
    
    try:
        from app import app, db, issue_signup_otp, verify_signup_otp, EmailVerifyOTP
        
        with app.app_context():
            test_email = "test@example.com"
            
            # Clean up any existing OTPs
            EmailVerifyOTP.query.filter_by(email=test_email).delete()
            db.session.commit()
            
            # Test OTP generation
            print("Generating OTP...")
            issue_signup_otp(test_email)
            
            # Check if OTP was created
            otp_record = EmailVerifyOTP.query.filter_by(email=test_email, used=False).first()
            if otp_record:
                print("[OK] OTP record created successfully!")
                print(f"   Email: {otp_record.email}")
                print(f"   Expires at: {otp_record.expires_at}")
                print(f"   Attempts: {otp_record.attempts}")
            else:
                print("[ERROR] OTP record not found!")
                return False
            
            # Test OTP verification with wrong code
            print("Testing wrong OTP...")
            success, message, _ = verify_signup_otp(test_email, "000000")
            if not success:
                print(f"[OK] Wrong OTP correctly rejected: {message}")
            else:
                print("[ERROR] Wrong OTP was accepted!")
                return False
            
            print("[OK] OTP functions working correctly!")
            
        return True
        
    except Exception as e:
        print(f"[ERROR] OTP function test failed: {e}")
        return False

def test_database_tables():
    """Test that all required tables exist"""
    print("\nTesting Database Tables...")
    
    try:
        from app import app, db
        from sqlalchemy import text
        
        with app.app_context():
            required_tables = [
                'users',
                'email_verify_otp',
                'reset_otp', 
                'delete_account_otp',
                'user_settings'
            ]
            
            for table in required_tables:
                result = db.session.execute(
                    text(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')")
                ).fetchone()
                
                if result[0]:
                    print(f"[OK] Table '{table}' exists")
                else:
                    print(f"[ERROR] Table '{table}' missing!")
                    return False
            
            print("[OK] All required tables exist!")
            
        return True
        
    except Exception as e:
        print(f"[ERROR] Database table test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing CalculatenTrade Email Verification System")
    print("=" * 60)
    
    tests = [
        ("Database Tables", test_database_tables),
        ("OTP Functions", test_otp_functions),
        ("Email Service", test_email_service),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\nRunning {test_name} Test...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"[ERROR] {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary:")
    print("-" * 30)
    
    all_passed = True
    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{test_name:20} {status}")
        if not passed:
            all_passed = False
    
    print("-" * 30)
    if all_passed:
        print("All tests passed! Email verification system is ready.")
        print("\nNext steps:")
        print("1. Start your Flask app: python app.py")
        print("2. Register a new user to test the full flow")
        print("3. Check your email for verification codes")
    else:
        print("Some tests failed. Please check the errors above.")
        print("Run setup_email_verification.py if database tables are missing.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)