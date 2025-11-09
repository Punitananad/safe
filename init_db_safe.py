#!/usr/bin/env python3
"""
Safe database initialization script with PostgreSQL compatibility fixes
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def init_database_safely():
    """Initialize database with proper error handling and type fixes"""
    try:
        # Apply PostgreSQL fixes first
        from postgresql_fix import apply_postgresql_fixes, fix_sqlalchemy_postgresql
        print("Applying PostgreSQL compatibility fixes...")
        apply_postgresql_fixes()
        fix_sqlalchemy_postgresql()
        
        # Import app after fixes are applied
        from app import app, db
        
        print("Creating database tables...")
        with app.app_context():
            # Create all tables
            db.create_all()
            print("✅ Database tables created successfully")
            
            # Initialize blueprint databases
            try:
                from admin_blueprint import init_admin_db
                init_admin_db(db)
                print("✅ Admin blueprint database initialized")
            except Exception as e:
                print(f"⚠️  Admin blueprint initialization warning: {e}")
            
            try:
                from employee_dashboard_bp import init_employee_dashboard_db
                init_employee_dashboard_db(db)
                print("✅ Employee dashboard blueprint database initialized")
            except Exception as e:
                print(f"⚠️  Employee dashboard initialization warning: {e}")
            
            try:
                from mentor import init_mentor_db
                init_mentor_db(db)
                print("✅ Mentor blueprint database initialized")
            except Exception as e:
                print(f"⚠️  Mentor blueprint initialization warning: {e}")
            
            try:
                from subscription_models import init_subscription_plans
                init_subscription_plans()
                print("✅ Subscription plans initialized")
            except Exception as e:
                print(f"⚠️  Subscription plans initialization warning: {e}")
            
            try:
                from broker_session_model import BrokerSession
                # Table is created by db.create_all() above
                print("✅ Broker session table initialized")
            except Exception as e:
                print(f"⚠️  Broker session initialization warning: {e}")
        
        print("\n🎉 Database initialization completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = init_database_safely()
    sys.exit(0 if success else 1)