#!/usr/bin/env python3
"""
Simple script to check MTF database schema
"""

import sqlite3
import os

def check_mtf_schema():
    """Check the MTF table schema in the database"""
    
    # Look for database files
    db_files = []
    for file in os.listdir('.'):
        if file.endswith('.db') or file.endswith('.sqlite'):
            db_files.append(file)
    
    if not db_files:
        print("No database files found in current directory")
        return False
    
    print(f"Found database files: {db_files}")
    
    for db_file in db_files:
        print(f"\nChecking database: {db_file}")
        
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Check if mtf_trades table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='mtf_trades'")
            table_exists = cursor.fetchone()
            
            if not table_exists:
                print(f"  mtf_trades table does not exist in {db_file}")
                continue
            
            print(f"  mtf_trades table found in {db_file}")
            
            # Get table schema
            cursor.execute("PRAGMA table_info(mtf_trades)")
            columns = cursor.fetchall()
            
            print("  Columns:")
            leverage_exists = False
            for col in columns:
                col_name = col[1]
                col_type = col[2]
                nullable = "NULL" if col[3] == 0 else "NOT NULL"
                print(f"    {col_name}: {col_type} ({nullable})")
                
                if col_name == 'leverage':
                    leverage_exists = True
            
            if leverage_exists:
                print("  ✓ leverage column exists")
            else:
                print("  ✗ leverage column is MISSING!")
                
                # Try to add the leverage column
                try:
                    cursor.execute("ALTER TABLE mtf_trades ADD COLUMN leverage FLOAT")
                    conn.commit()
                    print("  ✓ Added leverage column successfully")
                except Exception as e:
                    print(f"  ✗ Failed to add leverage column: {e}")
            
            conn.close()
            
        except Exception as e:
            print(f"  Error checking {db_file}: {e}")
    
    return True

def test_mtf_insert():
    """Test inserting MTF data"""
    
    # Find the main database
    db_files = [f for f in os.listdir('.') if f.endswith('.db')]
    if not db_files:
        print("No database files found")
        return False
    
    db_file = db_files[0]  # Use first database file
    print(f"\nTesting MTF insert in {db_file}")
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Test insert with leverage
        test_data = {
            'user_id': 1,
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
            'status': 'open',
            'timestamp': '2025-01-10 10:00:00'
        }
        
        # Build insert query
        columns = ', '.join(test_data.keys())
        placeholders = ', '.join(['?' for _ in test_data])
        query = f"INSERT INTO mtf_trades ({columns}) VALUES ({placeholders})"
        
        print(f"Insert query: {query}")
        print(f"Values: {list(test_data.values())}")
        
        cursor.execute(query, list(test_data.values()))
        conn.commit()
        
        print("✓ MTF insert successful!")
        
        # Get the inserted record
        cursor.execute("SELECT * FROM mtf_trades WHERE symbol = 'TESTSTOCK' ORDER BY id DESC LIMIT 1")
        record = cursor.fetchone()
        print(f"Inserted record: {record}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"✗ MTF insert failed: {e}")
        return False

if __name__ == "__main__":
    print("MTF Database Schema Checker")
    print("=" * 40)
    
    schema_ok = check_mtf_schema()
    
    if schema_ok:
        insert_ok = test_mtf_insert()
        
        if insert_ok:
            print("\n🎉 MTF database schema is working correctly!")
        else:
            print("\n⚠️ MTF insert test failed")
    else:
        print("\n⚠️ Schema check failed")