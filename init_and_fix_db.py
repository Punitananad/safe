#!/usr/bin/env python3
"""
Initialize database and fix MTF schema
"""

import os
import sys
from datetime import datetime, timezone

# Set environment variables before importing Flask app
os.environ['FLASK_ENV'] = 'development'

def init_database():
    """Initialize the database"""
    try:
        # Import after setting environment
        from app import app, db
        
        with app.app_context():
            print("Creating database tables...")
            db.create_all()
            print("Database tables created successfully!")
            
            # Check MTF table schema
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            
            if inspector.has_table('mtf_trades'):
                columns = inspector.get_columns('mtf_trades')
                print("\nMTF table columns:")
                leverage_exists = False
                for col in columns:
                    print(f"  {col['name']}: {col['type']}")
                    if col['name'] == 'leverage':
                        leverage_exists = True
                
                if leverage_exists:
                    print("leverage column exists in MTF table")
                else:
                    print("leverage column missing - this should not happen with current model")
            else:
                print("MTF table not found")
            
            return True
            
    except Exception as e:
        print(f"Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mtf_save():
    """Test MTF model saving"""
    try:
        from app import app, db, MTFTrade
        
        with app.app_context():
            print("\nTesting MTF model save...")
            
            # Create test MTF trade
            trade = MTFTrade(
                user_id=1,
                trade_type='buy',
                avg_price=100.0,
                quantity=10,
                expected_return=5.0,
                risk_percent=2.0,
                capital_used=250.0,
                target_price=105.0,
                stop_loss_price=98.0,
                total_reward=50.0,
                total_risk=20.0,
                rr_ratio=2.5,
                symbol='TESTSTOCK',
                comment='Test MTF trade',
                leverage=4.0,
                timestamp=datetime.now(timezone.utc)
            )
            
            db.session.add(trade)
            db.session.commit()
            
            print(f"MTF trade saved successfully with ID: {trade.id}")
            return True
            
    except Exception as e:
        print(f"Error testing MTF save: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("Database Initialization and MTF Fix Script")
    print("=" * 50)
    
    # Step 1: Initialize database
    init_success = init_database()
    
    if not init_success:
        print("Database initialization failed")
        return
    
    # Step 2: Test MTF save
    test_success = test_mtf_save()
    
    if test_success:
        print("\nSuccess! MTF trades should now save correctly.")
        print("Try saving an MTF trade from the web interface.")
    else:
        print("\nMTF save test failed. Check the errors above.")

if __name__ == "__main__":
    main()