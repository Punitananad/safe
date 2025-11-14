#!/usr/bin/env python3
"""
Script to verify MTF trade saving functionality and identify database issues
"""

import os
import sys
import requests
import json
from datetime import datetime

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_mtf_save_api():
    """Test the MTF save API endpoint directly"""
    url = "http://localhost:5000/save_mtf_result"
    
    # Sample MTF trade data
    test_data = {
        'trade_type': 'buy',
        'avg_price': 100.0,
        'quantity': 10,
        'expected_return': 5.0,
        'risk_percent': 2.0,
        'capital_used': 250.0,
        'target_price': 105.0,
        'stop_loss_price': 98.0,
        'total_reward': 50.0,
        'total_risk': 20.0,
        'rr_ratio': 2.5,
        'symbol': 'TESTSTOCK',
        'comment': 'Test MTF trade',
        'leverage': 4.0
    }
    
    print("Testing MTF save API...")
    print(f"URL: {url}")
    print(f"Data: {json.dumps(test_data, indent=2)}")
    
    try:
        response = requests.post(url, json=test_data, timeout=10)
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Text: {response.text}")
        
        if response.status_code == 200:
            print("✅ MTF save successful!")
            return True
        else:
            print("❌ MTF save failed!")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

def check_database_schema():
    """Check the MTF table schema"""
    try:
        from app import app, db, MTFTrade
        
        with app.app_context():
            print("\nChecking MTF table schema...")
            
            # Get table columns
            inspector = db.inspect(db.engine)
            columns = inspector.get_columns('mtf_trades')
            
            print("MTF table columns:")
            for col in columns:
                print(f"  - {col['name']}: {col['type']} (nullable: {col['nullable']})")
            
            # Check if leverage column exists
            leverage_exists = any(col['name'] == 'leverage' for col in columns)
            print(f"\nLeverage column exists: {leverage_exists}")
            
            if not leverage_exists:
                print("❌ ISSUE FOUND: leverage column is missing from mtf_trades table!")
                return False
            else:
                print("✅ leverage column exists in mtf_trades table")
                return True
                
    except Exception as e:
        print(f"❌ Error checking database schema: {e}")
        return False

def test_mtf_model_creation():
    """Test creating MTF model instance directly"""
    try:
        from app import app, db, MTFTrade
        
        with app.app_context():
            print("\nTesting MTF model creation...")
            
            # Test data
            test_data = {
                'user_id': 1,  # Assuming user ID 1 exists
                'trade_type': 'buy',
                'avg_price': 100.0,
                'quantity': 10,
                'expected_return': 5.0,
                'risk_percent': 2.0,
                'capital_used': 250.0,
                'target_price': 105.0,
                'stop_loss_price': 98.0,
                'total_reward': 50.0,
                'total_risk': 20.0,
                'rr_ratio': 2.5,
                'symbol': 'TESTSTOCK',
                'comment': 'Test MTF trade',
                'leverage': 4.0,
                'timestamp': datetime.utcnow()
            }
            
            # Try to create MTF trade instance
            trade = MTFTrade(**test_data)
            print("✅ MTF model instance created successfully")
            
            # Try to add to session
            db.session.add(trade)
            print("✅ MTF trade added to session")
            
            # Try to commit
            db.session.commit()
            print("✅ MTF trade committed to database")
            
            print(f"Trade ID: {trade.id}")
            return True
            
    except Exception as e:
        print(f"❌ Error creating MTF model: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return False

def run_database_migration():
    """Run database migration to add missing columns"""
    try:
        from app import app, db
        
        with app.app_context():
            print("\nRunning database migration...")
            
            # Check if leverage column exists
            inspector = db.inspect(db.engine)
            columns = inspector.get_columns('mtf_trades')
            leverage_exists = any(col['name'] == 'leverage' for col in columns)
            
            if not leverage_exists:
                print("Adding leverage column to mtf_trades table...")
                db.engine.execute('ALTER TABLE mtf_trades ADD COLUMN leverage FLOAT')
                print("✅ leverage column added successfully")
            else:
                print("✅ leverage column already exists")
            
            return True
            
    except Exception as e:
        print(f"❌ Error running migration: {e}")
        return False

def main():
    """Main verification function"""
    print("=" * 60)
    print("MTF TRADE SAVE VERIFICATION SCRIPT")
    print("=" * 60)
    
    # Step 1: Check database schema
    schema_ok = check_database_schema()
    
    # Step 2: If schema issue, try to fix it
    if not schema_ok:
        print("\nAttempting to fix database schema...")
        migration_ok = run_database_migration()
        if migration_ok:
            schema_ok = check_database_schema()
    
    # Step 3: Test model creation
    if schema_ok:
        model_ok = test_mtf_model_creation()
    else:
        model_ok = False
    
    # Step 4: Test API endpoint
    if model_ok:
        api_ok = test_mtf_save_api()
    else:
        api_ok = False
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"Database Schema: {'✅ OK' if schema_ok else '❌ FAILED'}")
    print(f"Model Creation:  {'✅ OK' if model_ok else '❌ FAILED'}")
    print(f"API Endpoint:    {'✅ OK' if api_ok else '❌ FAILED'}")
    
    if all([schema_ok, model_ok, api_ok]):
        print("\n🎉 All tests passed! MTF save should work correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the issues above.")
    
    return all([schema_ok, model_ok, api_ok])

if __name__ == "__main__":
    main()