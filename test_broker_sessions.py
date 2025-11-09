#!/usr/bin/env python3
"""
Test broker session persistence
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_broker_sessions():
    """Test broker session save and retrieve"""
    try:
        from app import app, db
        from broker_session_model import save_session, get_active_session
        
        with app.app_context():
            # Test data
            user_email = "test@example.com"
            broker = "kite"
            user_id = "test_user"
            session_data = {
                "access_token": "test_token_123",
                "kite_user_id": "test_kite_user"
            }
            
            # Save session
            print("Saving test session...")
            session = save_session(user_email, broker, user_id, session_data, remember_session=True)
            print(f"Session saved with ID: {session.id}")
            
            # Retrieve session
            print("Retrieving session...")
            retrieved = get_active_session(user_email, broker, user_id)
            
            if retrieved:
                print(f"Session retrieved: {retrieved.to_dict()}")
                print("[SUCCESS] Session persistence working!")
                
                # Clean up test data
                db.session.delete(retrieved)
                db.session.commit()
                print("Test data cleaned up")
                
                return True
            else:
                print("[ERROR] Failed to retrieve session")
                return False
                
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_broker_sessions()
    sys.exit(0 if success else 1)