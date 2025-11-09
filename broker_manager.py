"""
Advanced Broker Connection Manager
Handles persistent sessions, credentials management, and broker API integrations
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import hashlib
import base64
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

class BrokerManager:
    def __init__(self, app=None):
        self.app = app
        self.sessions = {}
        self.credentials_store = {}
        self.encryption_key = None
        self.init_encryption()
        
    def init_encryption(self):
        """Initialize encryption for storing sensitive credentials"""
        key_file = "broker_key.key"
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                self.encryption_key = f.read()
        else:
            self.encryption_key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(self.encryption_key)
        self.cipher = Fernet(self.encryption_key)
    
    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data"""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()
    
    def save_credentials(self, broker: str, user_id: str, credentials: Dict[str, Any]) -> bool:
        """Save encrypted broker credentials"""
        try:
            key = f"{broker}_{user_id}"
            encrypted_creds = {}
            
            for field, value in credentials.items():
                if field in ['api_key', 'api_secret', 'access_token', 'client_id']:
                    encrypted_creds[field] = self.encrypt_data(str(value))
                else:
                    encrypted_creds[field] = value
            
            encrypted_creds['saved_at'] = datetime.now().isoformat()
            encrypted_creds['broker'] = broker
            encrypted_creds['user_id'] = user_id
            
            self.credentials_store[key] = encrypted_creds
            self._save_credentials_to_file()
            return True
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            return False
    
    def load_credentials(self, broker: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Load and decrypt broker credentials"""
        try:
            key = f"{broker}_{user_id}"
            if key not in self.credentials_store:
                self._load_credentials_from_file()
            
            if key in self.credentials_store:
                encrypted_creds = self.credentials_store[key]
                decrypted_creds = {}
                
                for field, value in encrypted_creds.items():
                    if field in ['api_key', 'api_secret', 'access_token', 'client_id']:
                        decrypted_creds[field] = self.decrypt_data(value)
                    else:
                        decrypted_creds[field] = value
                
                return decrypted_creds
            return None
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return None
    
    def _save_credentials_to_file(self):
        """Save credentials store to file"""
        try:
            with open('broker_credentials.json', 'w') as f:
                json.dump(self.credentials_store, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save credentials file: {e}")
    
    def _load_credentials_from_file(self):
        """Load credentials store from file"""
        try:
            if os.path.exists('broker_credentials.json'):
                with open('broker_credentials.json', 'r') as f:
                    self.credentials_store = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load credentials file: {e}")
    
    def create_session(self, broker: str, user_id: str, session_data: Dict[str, Any]) -> str:
        """Create a persistent broker session"""
        session_id = hashlib.md5(f"{broker}_{user_id}_{time.time()}".encode()).hexdigest()
        
        self.sessions[session_id] = {
            'broker': broker,
            'user_id': user_id,
            'created_at': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(hours=24)).isoformat(),
            'status': 'active',
            **session_data
        }
        
        self._save_sessions_to_file()
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        if session_id not in self.sessions:
            self._load_sessions_from_file()
        
        if session_id in self.sessions:
            session = self.sessions[session_id]
            
            # Check if session is expired
            expires_at = datetime.fromisoformat(session['expires_at'])
            if datetime.now() > expires_at:
                session['status'] = 'expired'
                self._save_sessions_to_file()
                return None
            
            # Update last activity
            session['last_activity'] = datetime.now().isoformat()
            self._save_sessions_to_file()
            return session
        
        return None
    
    def get_active_session(self, broker: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get active session for broker/user combination"""
        self._load_sessions_from_file()
        
        for session_id, session in self.sessions.items():
            if (session['broker'] == broker and 
                session['user_id'] == user_id and 
                session['status'] == 'active'):
                
                # Check if expired
                expires_at = datetime.fromisoformat(session['expires_at'])
                if datetime.now() > expires_at:
                    session['status'] = 'expired'
                    continue
                
                return session
        
        return None
    
    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session"""
        if session_id in self.sessions:
            self.sessions[session_id]['status'] = 'invalidated'
            self.sessions[session_id]['invalidated_at'] = datetime.now().isoformat()
            self._save_sessions_to_file()
            return True
        return False
    
    def invalidate_user_sessions(self, broker: str, user_id: str) -> int:
        """Invalidate all sessions for a user/broker"""
        count = 0
        for session_id, session in self.sessions.items():
            if (session['broker'] == broker and 
                session['user_id'] == user_id and 
                session['status'] == 'active'):
                session['status'] = 'invalidated'
                session['invalidated_at'] = datetime.now().isoformat()
                count += 1
        
        if count > 0:
            self._save_sessions_to_file()
        return count
    
    def _save_sessions_to_file(self):
        """Save sessions to file"""
        try:
            with open('broker_sessions.json', 'w') as f:
                json.dump(self.sessions, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save sessions file: {e}")
    
    def _load_sessions_from_file(self):
        """Load sessions from file"""
        try:
            if os.path.exists('broker_sessions.json'):
                with open('broker_sessions.json', 'r') as f:
                    self.sessions = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load sessions file: {e}")
    
    def get_remembered_accounts(self) -> List[Dict[str, Any]]:
        """Get list of remembered accounts"""
        self._load_credentials_from_file()
        accounts = []
        
        for key, creds in self.credentials_store.items():
            accounts.append({
                'broker': creds['broker'],
                'user_id': creds['user_id'],
                'saved_at': creds.get('saved_at'),
                'key': key
            })
        
        return sorted(accounts, key=lambda x: x['saved_at'], reverse=True)
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        now = datetime.now()
        expired_count = 0
        
        for session_id, session in list(self.sessions.items()):
            expires_at = datetime.fromisoformat(session['expires_at'])
            if now > expires_at:
                session['status'] = 'expired'
                expired_count += 1
        
        if expired_count > 0:
            self._save_sessions_to_file()
            logger.info(f"Cleaned up {expired_count} expired sessions")
        
        return expired_count

# Global broker manager instance
broker_manager = BrokerManager()