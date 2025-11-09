#!/usr/bin/env python3
"""
Fix Dhan Token Integration
This script ensures the Dhan token from dhan_token.json is properly integrated with the broker system.
"""

import json
import os
from datetime import datetime, timedelta

def load_dhan_token():
    """Load token from dhan_token.json"""
    try:
        if os.path.exists('dhan_token.json'):
            with open('dhan_token.json', 'r') as f:
                data = json.load(f)
                return data.get('access_token'), data.get('expires_at')
    except Exception as e:
        print(f"Error loading dhan_token.json: {e}")
    return None, None

def update_env_file():
    """Update .env file with Dhan token"""
    token, expires_at = load_dhan_token()
    if not token:
        print("No valid token found in dhan_token.json")
        return False
    
    # Check if token is expired
    if expires_at and expires_at < int(datetime.now().timestamp()):
        print("Token in dhan_token.json is expired")
        return False
    
    # Read current .env file
    env_lines = []
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            env_lines = f.readlines()
    
    # Update or add DHAN_ACCESS_TOKEN
    token_found = False
    for i, line in enumerate(env_lines):
        if line.startswith('DHAN_ACCESS_TOKEN='):
            env_lines[i] = f'DHAN_ACCESS_TOKEN={token}\n'
            token_found = True
            break
    
    if not token_found:
        env_lines.append(f'DHAN_ACCESS_TOKEN={token}\n')
    
    # Write back to .env
    with open('.env', 'w') as f:
        f.writelines(env_lines)
    
    print(f"Updated .env with Dhan token (expires: {datetime.fromtimestamp(expires_at) if expires_at else 'unknown'})")
    return True

def create_broker_session():
    """Create a broker session with the current token"""
    try:
        from broker_manager import broker_manager
        
        token, expires_at = load_dhan_token()
        if not token:
            print("No token available")
            return False
        
        # Get client ID from .env
        from dotenv import load_dotenv
        load_dotenv()
        client_id = os.getenv('DHAN_CLIENT_ID')
        
        if not client_id:
            print("DHAN_CLIENT_ID not found in .env")
            return False
        
        # Save credentials to broker manager
        credentials = {
            'client_id': client_id,
            'access_token': token,
            'user_id': client_id
        }
        
        success = broker_manager.save_credentials('dhan', client_id, credentials)
        if success:
            print(f"Saved Dhan credentials for client {client_id}")
            
            # Create active session
            session_data = {
                'access_token': token,
                'client_id': client_id,
                'session_id': f"dhan_{client_id}_{int(datetime.now().timestamp())}",
                'status': 'active',
                'created_at': datetime.now().isoformat(),
                'expires_at': datetime.fromtimestamp(expires_at).isoformat() if expires_at else (datetime.now() + timedelta(hours=24)).isoformat()
            }
            
            session_id = broker_manager.create_session('dhan', client_id, session_data)
            print(f"Created Dhan session: {session_id}")
            return True
        else:
            print("Failed to save credentials")
            return False
            
    except Exception as e:
        print(f"Error creating broker session: {e}")
        return False

if __name__ == "__main__":
    print("Fixing Dhan token integration...")
    
    # Step 1: Update .env file
    if update_env_file():
        print("✓ Updated .env file")
    else:
        print("✗ Failed to update .env file")
        exit(1)
    
    # Step 2: Create broker session
    if create_broker_session():
        print("✓ Created broker session")
    else:
        print("✗ Failed to create broker session")
    
    print("Done! Your Dhan token should now work properly.")