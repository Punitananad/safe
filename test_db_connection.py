#!/usr/bin/env python3
"""
Test database connection and PostgreSQL type compatibility
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_database_connection():
    """Test database connection and query execution"""
    try:
        # Apply PostgreSQL fixes first
        print("Applying PostgreSQL compatibility fixes...")
        from postgresql_fix import apply_postgresql_fixes, fix_sqlalchemy_postgresql
        apply_postgresql_fixes()
        fix_sqlalchemy_postgresql()
        
        # Import app components
        from app import app, db
        from journal import Mistake
        
        print("Testing database connection...")
        
        with app.app_context():
            # Test basic connection
            try:
                # Try to execute a simple query that was failing
                mistakes = Mistake.query.order_by(Mistake.created_at.desc()).limit(1).all()
                print(f"✅ Successfully queried Mistake table, found {len(mistakes)} records")
                
                # Test other common queries
                mistake_count = Mistake.query.count()
                print(f"✅ Total mistakes in database: {mistake_count}")
                
                # Test database engine
                result = db.engine.execute("SELECT version()")
                version = result.fetchone()[0]
                print(f"✅ PostgreSQL version: {version}")
                
                print("\n🎉 All database tests passed!")
                return True
                
            except Exception as e:
                print(f"❌ Database query failed: {e}")
                import traceback
                traceback.print_exc()
                return False
                
    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_database_connection()
    print(f"\nTest result: {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)