#!/usr/bin/env python3
"""
Debug session configuration
"""

import requests
import sys

def debug_session():
    """Debug session configuration"""
    base_url = "http://localhost:5000"
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    print("Debugging Session Configuration...")
    print("=" * 50)
    
    # Step 1: Check if Flask app is running
    print("1. Checking Flask app status...")
    try:
        response = session.get(f"{base_url}/")
        print(f"Flask app running: {response.status_code == 200}")
    except Exception as e:
        print(f"Flask app not accessible: {e}")
        return False
    
    # Step 2: Test session setting via test route
    print("2. Testing session setting...")
    try:
        response = session.get(f"{base_url}/admin/test-login")
        if response.status_code == 200:
            result = response.json()
            print(f"Test login result: {result}")
        else:
            print(f"Test login failed: {response.status_code}")
    except Exception as e:
        print(f"Test login error: {e}")
    
    # Step 3: Check session immediately after setting
    print("3. Checking session after setting...")
    try:
        response = session.get(f"{base_url}/admin/test-session")
        if response.status_code == 200:
            session_data = response.json()
            print("Session data after setting:")
            for key, value in session_data.items():
                print(f"  {key}: {value}")
        else:
            print(f"Session check failed: {response.status_code}")
    except Exception as e:
        print(f"Session check error: {e}")
    
    # Step 4: Try accessing dashboard with test session
    print("4. Testing dashboard access with test session...")
    try:
        response = session.get(f"{base_url}/admin/dashboard", allow_redirects=False)
        print(f"Dashboard response: {response.status_code}")
        if response.status_code in [302, 303]:
            redirect_url = response.headers.get('Location', '')
            print(f"Dashboard redirected to: {redirect_url}")
        elif response.status_code == 200:
            print("Dashboard accessible!")
    except Exception as e:
        print(f"Dashboard access error: {e}")
    
    return True

if __name__ == "__main__":
    debug_session()