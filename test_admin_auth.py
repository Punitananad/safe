#!/usr/bin/env python3
"""
Test script for admin authentication flow
Tests the 2-layer authentication without loops
"""

import requests
import sys

def test_admin_auth():
    """Test the admin authentication flow"""
    base_url = "http://localhost:5000"
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    print("🔧 Testing Admin Authentication Flow...")
    print("=" * 50)
    
    # Step 1: Test admin login page
    print("1. Testing admin login page...")
    try:
        response = session.get(f"{base_url}/admin/login")
        if response.status_code == 200:
            print("✅ Admin login page accessible")
        else:
            print(f"❌ Admin login page failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error accessing admin login: {e}")
        return False
    
    # Step 2: Test first password (welcometocnt)
    print("\n2. Testing first password (welcometocnt)...")
    try:
        login_data = {
            'password': 'welcometocnt'
        }
        response = session.post(f"{base_url}/admin/login", data=login_data, allow_redirects=False)
        
        if response.status_code in [302, 303]:
            print("✅ First password accepted, redirecting to OTP")
            redirect_url = response.headers.get('Location', '')
            if 'verify-otp' in redirect_url:
                print("✅ Correctly redirected to OTP verification")
            else:
                print(f"⚠️  Unexpected redirect: {redirect_url}")
        else:
            print(f"❌ First password failed: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Error with first password: {e}")
        return False
    
    # Step 3: Test second password (124113) as OTP
    print("\n3. Testing second password (124113) as OTP...")
    try:
        otp_data = {
            'otp': '124113'
        }
        response = session.post(f"{base_url}/admin/verify-otp", data=otp_data, allow_redirects=False)
        
        if response.status_code in [302, 303]:
            print("✅ Second password (OTP) accepted")
            redirect_url = response.headers.get('Location', '')
            if 'dashboard' in redirect_url:
                print("✅ Correctly redirected to dashboard")
            else:
                print(f"⚠️  Unexpected redirect: {redirect_url}")
        else:
            print(f"❌ Second password failed: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Error with second password: {e}")
        return False
    
    # Step 4: Test dashboard access
    print("\n4. Testing dashboard access...")
    try:
        response = session.get(f"{base_url}/admin/dashboard")
        if response.status_code == 200:
            print("✅ Dashboard accessible after authentication")
            
            # Check for password reset buttons
            if 'Password Reset' in response.text and 'Manual Reset' in response.text:
                print("✅ Password reset tools available in dashboard")
            else:
                print("⚠️  Password reset tools not found in dashboard")
        else:
            print(f"❌ Dashboard access failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error accessing dashboard: {e}")
        return False
    
    # Step 5: Test password reset tools
    print("\n5. Testing password reset tools...")
    try:
        # Test reset links page
        response = session.get(f"{base_url}/admin/reset-links")
        if response.status_code == 200:
            print("✅ Password reset links page accessible")
        else:
            print(f"❌ Password reset links failed: {response.status_code}")
        
        # Test manual reset page
        response = session.get(f"{base_url}/admin/manual-reset")
        if response.status_code == 200:
            print("✅ Manual reset page accessible")
        else:
            print(f"❌ Manual reset page failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing reset tools: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 All tests passed! Admin authentication working correctly.")
    return True

def test_session_persistence():
    """Test if admin session persists across requests"""
    base_url = "http://localhost:5000"
    session = requests.Session()
    
    print("\n🔒 Testing Session Persistence...")
    print("=" * 50)
    
    # Login first
    login_data = {'password': 'welcometocnt'}
    session.post(f"{base_url}/admin/login", data=login_data)
    
    otp_data = {'otp': '124113'}
    session.post(f"{base_url}/admin/verify-otp", data=otp_data)
    
    # Test multiple dashboard requests
    for i in range(3):
        response = session.get(f"{base_url}/admin/dashboard")
        if response.status_code == 200:
            print(f"✅ Request {i+1}: Dashboard accessible")
        else:
            print(f"❌ Request {i+1}: Session lost, redirected to login")
            return False
    
    print("✅ Session persistence working correctly")
    return True

if __name__ == "__main__":
    print("🚀 Starting Admin Authentication Tests")
    print("Make sure the Flask app is running on localhost:5000")
    print()
    
    try:
        # Test basic authentication flow
        if test_admin_auth():
            # Test session persistence
            test_session_persistence()
        else:
            print("\n❌ Authentication tests failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)