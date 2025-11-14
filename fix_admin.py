#!/usr/bin/env python3
"""
Quick fix for admin authentication by creating a direct route
"""

import requests

def test_direct_admin():
    """Test direct admin access"""
    base_url = "http://localhost:5000"
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    print("Testing Direct Admin Access...")
    print("=" * 50)
    
    # Test the direct admin route with both passwords
    print("1. Testing direct admin access with both passwords...")
    
    # First password
    login_data = {'password': 'welcometocnt'}
    response = session.post(f"{base_url}/admin/login", data=login_data, allow_redirects=True)
    print(f"After first password: {response.status_code}, URL: {response.url}")
    
    # Second password (OTP)
    if 'verify-otp' in response.url:
        otp_data = {'otp': '124113'}
        response = session.post(f"{base_url}/admin/verify-otp", data=otp_data, allow_redirects=True)
        print(f"After second password: {response.status_code}, URL: {response.url}")
        
        if 'dashboard' in response.url:
            print("SUCCESS: Reached dashboard!")
            return True
        else:
            print(f"FAIL: Did not reach dashboard, at: {response.url}")
            return False
    else:
        print(f"FAIL: Did not reach OTP page, at: {response.url}")
        return False

if __name__ == "__main__":
    test_direct_admin()