#!/usr/bin/env python3
"""
Test session persistence for admin authentication
"""

import requests
import sys

def test_session_persistence():
    """Test if admin session persists across requests"""
    base_url = "http://localhost:5000"
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    print("Testing Admin Session Persistence...")
    print("=" * 50)
    
    # Step 1: Login with first password
    print("1. Logging in with first password...")
    login_data = {'password': 'welcometocnt'}
    response = session.post(f"{base_url}/admin/login", data=login_data, allow_redirects=False)
    print(f"Login response: {response.status_code}")
    
    # Step 2: Verify OTP with second password
    print("2. Verifying OTP with second password...")
    otp_data = {'otp': '124113'}
    response = session.post(f"{base_url}/admin/verify-otp", data=otp_data, allow_redirects=False)
    print(f"OTP response: {response.status_code}")
    print(f"Redirect location: {response.headers.get('Location', 'None')}")
    
    # Step 3: Check session status
    print("3. Checking session status...")
    response = session.get(f"{base_url}/admin/debug-session")
    if response.status_code == 200:
        session_data = response.json()
        print("Session data:")
        for key, value in session_data.items():
            print(f"  {key}: {value}")
    else:
        print(f"Failed to get session data: {response.status_code}")
    
    # Step 4: Try to access dashboard directly
    print("4. Accessing dashboard...")
    response = session.get(f"{base_url}/admin/dashboard", allow_redirects=False)
    print(f"Dashboard response: {response.status_code}")
    
    if response.status_code == 200:
        print("SUCCESS: Dashboard accessible!")
        return True
    elif response.status_code in [302, 303]:
        redirect_url = response.headers.get('Location', '')
        print(f"REDIRECT: Dashboard redirected to {redirect_url}")
        if 'login' in redirect_url:
            print("FAIL: Redirected back to login - session not persisting")
            return False
        else:
            print("INFO: Redirected to different page")
            return True
    else:
        print(f"FAIL: Unexpected response code: {response.status_code}")
        return False

if __name__ == "__main__":
    print("Starting Session Persistence Test")
    print("Make sure the Flask app is running on localhost:5000")
    print()
    
    try:
        success = test_session_persistence()
        if success:
            print("\nSUCCESS: Session persistence working!")
        else:
            print("\nFAIL: Session persistence not working!")
            sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)