#!/usr/bin/env python3
"""
Add broker_sessions table to existing database
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def add_broker_sessions_table():
    """Add broker_sessions table to database"""
    try:
        from app import app, db
        from broker_session_model import BrokerSession
        
        with app.app_context():
            # Create the broker_sessions table
            db.create_all()
            print("[SUCCESS] Broker sessions table added successfully")
            
            # Test the table
            from broker_session_model import save_session, get_active_session
            print("[SUCCESS] Broker session functions working")
            
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to add broker sessions table: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = add_broker_sessions_table()
    sys.exit(0 if success else 1)