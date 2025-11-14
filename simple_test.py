#!/usr/bin/env python3
"""
Simple test script for admin authentication flow
"""

import requests
import sys

def test_admin_auth():
    """Test the admin authentication flow"""
    base_url = "http://localhost:5000"
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    print("Testing Admin Authentication Flow...")
    print("=" * 50)
    
    # Step 1: Test admin login page
    print("1. Testing admin login page...")
    try:
        response = session.get(f"{base_url}/admin/login")
        if response.status_code == 200:
            print("PASS: Admin login page accessible")
        else:
            print(f"FAIL: Admin login page failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"FAIL: Error accessing admin login: {e}")
        return False
    
    # Step 2: Test first password (welcometocnt)
    print("\n2. Testing first password (welcometocnt)...")
    try:
        login_data = {
            'password': 'welcometocnt'
        }
        response = session.post(f"{base_url}/admin/login", data=login_data, allow_redirects=False)
        
        if response.status_code in [302, 303]:
            print("PASS: First password accepted, redirecting to OTP")
            redirect_url = response.headers.get('Location', '')
            if 'verify-otp' in redirect_url:
                print("PASS: Correctly redirected to OTP verification")
            else:
                print(f"WARN: Unexpected redirect: {redirect_url}")
        else:
            print(f"FAIL: First password failed: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"FAIL: Error with first password: {e}")
        return False
    
    # Step 3: Test second password (124113) as OTP
    print("\n3. Testing second password (124113) as OTP...")
    try:
        otp_data = {
            'otp': '124113'
        }
        response = session.post(f"{base_url}/admin/verify-otp", data=otp_data, allow_redirects=False)
        
        if response.status_code in [302, 303]:
            print("PASS: Second password (OTP) accepted")
            redirect_url = response.headers.get('Location', '')
            if 'dashboard' in redirect_url:
                print("PASS: Correctly redirected to dashboard")
            else:
                print(f"WARN: Unexpected redirect: {redirect_url}")
        else:
            print(f"FAIL: Second password failed: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"FAIL: Error with second password: {e}")
        return False
    
    # Step 4: Test dashboard access
    print("\n4. Testing dashboard access...")
    try:
        response = session.get(f"{base_url}/admin/dashboard")
        if response.status_code == 200:
            print("PASS: Dashboard accessible after authentication")
            
            # Check for password reset buttons
            if 'Password Reset' in response.text and 'Manual Reset' in response.text:
                print("PASS: Password reset tools available in dashboard")
            else:
                print("WARN: Password reset tools not found in dashboard")
        else:
            print(f"FAIL: Dashboard access failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"FAIL: Error accessing dashboard: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("SUCCESS: All tests passed! Admin authentication working correctly.")
    return True

if __name__ == "__main__":
    print("Starting Admin Authentication Tests")
    print("Make sure the Flask app is running on localhost:5000")
    print()
    
    try:
        test_admin_auth()
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\nFAIL: Unexpected error: {e}")
        sys.exit(1)