"""
Token storage utilities for Dhan API access tokens
Provides persistent token storage with expiration handling
"""

import os
import json
import time
from datetime import datetime, timedelta

TOKEN_FILE = "dhan_token.json"

def save_token(access_token: str, expires_in_seconds: int = 86400):
    """Save access token with expiration time"""
    expires_at = time.time() + expires_in_seconds
    token_data = {
        "access_token": access_token,
        "expires_at": expires_at,
        "saved_at": datetime.now().isoformat()
    }
    
    try:
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token_data, f, indent=2)
        print(f"Token saved successfully, expires at: {datetime.fromtimestamp(expires_at)}")
    except Exception as e:
        print(f"Error saving token: {e}")

def get_token():
    """Get valid access token, returns None if expired or missing"""
    # First try to get from JSON file
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                token_data = json.load(f)
            
            access_token = token_data.get("access_token")
            expires_at = token_data.get("expires_at", 0)
            
            # Check if token is still valid
            if access_token and time.time() < expires_at:
                return access_token
            else:
                print("Token from file is expired")
        except Exception as e:
            print(f"Error reading token file: {e}")
    
    # Fallback to environment variable
    env_token = os.getenv("DHAN_ACCESS_TOKEN")
    if env_token:
        print("Using token from environment variable")
        return env_token
    
    print("No valid token found")
    return None

def is_token_valid():
    """Check if current token is valid"""
    return get_token() is not None

def get_token_info():
    """Get token information for debugging"""
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                token_data = json.load(f)
            
            expires_at = token_data.get("expires_at", 0)
            saved_at = token_data.get("saved_at", "unknown")
            
            return {
                "source": "file",
                "expires_at": datetime.fromtimestamp(expires_at).isoformat() if expires_at else None,
                "saved_at": saved_at,
                "is_valid": time.time() < expires_at if expires_at else False
            }
        except Exception as e:
            return {"source": "file", "error": str(e)}
    
    env_token = os.getenv("DHAN_ACCESS_TOKEN")
    if env_token:
        return {
            "source": "environment",
            "is_valid": True,
            "note": "Environment tokens don't have expiration tracking"
        }
    
    return {"source": "none", "is_valid": False}