#!/usr/bin/env python3
"""
Simple test for PostgreSQL type compatibility fix
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_mistake_query():
    """Test the specific query that was failing"""
    try:
        # Import the fix first
        import pg_type_fix
        print("PostgreSQL fix imported")
        
        # Import app components
        from app import app, db
        from journal import Mistake
        
        print("Testing Mistake query...")
        
        with app.app_context():
            try:
                # This is the exact query that was failing
                mistakes = Mistake.query.order_by(Mistake.created_at.desc()).all()
                print(f"SUCCESS: Found {len(mistakes)} mistakes")
                return True
                
            except Exception as e:
                print(f"FAILED: {e}")
                return False
                
    except Exception as e:
        print(f"Setup failed: {e}")
        return False

if __name__ == "__main__":
    success = test_mistake_query()
    print(f"Test result: {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)