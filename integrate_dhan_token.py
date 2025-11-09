#!/usr/bin/env python3
"""
Integrate Dhan Token with Broker System
This script helps users integrate their existing Dhan token with the broker connection system.
"""

import json
import os
from datetime import datetime, timedelta

def integrate_dhan_token():
    """Integrate existing Dhan token with broker system"""
    
    # Load token from dhan_token.json
    if not os.path.exists('dhan_token.json'):
        print("❌ dhan_token.json not found!")
        return False
    
    try:
        with open('dhan_token.json', 'r') as f:
            token_data = json.load(f)
        
        access_token = token_data.get('access_token')
        expires_at = token_data.get('expires_at')
        
        if not access_token:
            print("❌ No access_token found in dhan_token.json")
            return False
        
        # Check if token is expired
        if expires_at and expires_at < int(datetime.now().timestamp()):
            print("❌ Token in dhan_token.json is expired")
            return False
        
        print(f"✅ Found valid Dhan token (expires: {datetime.fromtimestamp(expires_at) if expires_at else 'unknown'})")
        
    except Exception as e:
        print(f"❌ Error reading dhan_token.json: {e}")
        return False
    
    # Get client ID from .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
        client_id = os.getenv('DHAN_CLIENT_ID')
        
        if not client_id:
            print("❌ DHAN_CLIENT_ID not found in .env file")
            return False
        
        print(f"✅ Found Dhan Client ID: {client_id}")
        
    except Exception as e:
        print(f"❌ Error loading .env: {e}")
        return False
    
    # Update .env with access token
    try:
        env_lines = []
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                env_lines = f.readlines()
        
        # Update or add DHAN_ACCESS_TOKEN
        token_found = False
        for i, line in enumerate(env_lines):
            if line.startswith('DHAN_ACCESS_TOKEN='):
                env_lines[i] = f'DHAN_ACCESS_TOKEN={access_token}\n'
                token_found = True
                break
        
        if not token_found:
            env_lines.append(f'DHAN_ACCESS_TOKEN={access_token}\n')
        
        # Write back to .env
        with open('.env', 'w') as f:
            f.writelines(env_lines)
        
        print("✅ Updated .env with Dhan access token")
        
    except Exception as e:
        print(f"❌ Error updating .env: {e}")
        return False
    
    # Create broker credentials file
    try:
        from broker_manager import broker_manager
        
        # Save credentials to broker manager
        credentials = {
            'client_id': client_id,
            'access_token': access_token,
            'user_id': client_id
        }
        
        success = broker_manager.save_credentials('dhan', client_id, credentials)
        if success:
            print(f"✅ Saved Dhan credentials for client {client_id}")
            
            # Create active session
            session_data = {
                'access_token': access_token,
                'client_id': client_id,
                'session_id': f"dhan_{client_id}_{int(datetime.now().timestamp())}",
                'status': 'active',
                'created_at': datetime.now().isoformat(),
                'expires_at': datetime.fromtimestamp(expires_at).isoformat() if expires_at else (datetime.now() + timedelta(hours=24)).isoformat()
            }
            
            session_id = broker_manager.create_session('dhan', client_id, session_data)
            print(f"✅ Created Dhan session: {session_id}")
            
            return True
        else:
            print("❌ Failed to save credentials to broker manager")
            return False
            
    except Exception as e:
        print(f"❌ Error creating broker session: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Integrating Dhan Token with Broker System...")
    print("=" * 50)
    
    if integrate_dhan_token():
        print("=" * 50)
        print("🎉 SUCCESS! Your Dhan token has been integrated.")
        print("\nNext steps:")
        print("1. Go to the broker connection page")
        print("2. Select 'Dhan' as broker")
        print("3. Enter your Client ID in the User ID field")
        print("4. Click 'Connect' (no need to register again)")
        print("\nYour token should now work properly!")
    else:
        print("=" * 50)
        print("❌ FAILED! Could not integrate Dhan token.")
        print("\nPlease check:")
        print("1. dhan_token.json exists and has valid token")
        print("2. .env file has DHAN_CLIENT_ID")
        print("3. broker_manager.py is working properly")