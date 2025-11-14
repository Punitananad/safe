#!/usr/bin/env python3
"""
Fix MTF database schema issues
"""

import sqlite3
import os

def find_database():
    """Find the database file"""
    possible_paths = [
        'instance/database.db',
        'instance/app.db',
        'database.db',
        'app.db'
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"Found database: {path}")
            return path
    
    print("No database file found")
    return None

def check_and_fix_mtf_table(db_path):
    """Check and fix MTF table schema"""
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if mtf_trades table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='mtf_trades'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("mtf_trades table does not exist")
            conn.close()
            return False
        
        print("mtf_trades table found")
        
        # Get current schema
        cursor.execute("PRAGMA table_info(mtf_trades)")
        columns = cursor.fetchall()
        
        print("Current columns:")
        leverage_exists = False
        for col in columns:
            col_name = col[1]
            col_type = col[2]
            print(f"  {col_name}: {col_type}")
            
            if col_name == 'leverage':
                leverage_exists = True
        
        if not leverage_exists:
            print("Adding leverage column...")
            cursor.execute("ALTER TABLE mtf_trades ADD COLUMN leverage FLOAT")
            conn.commit()
            print("leverage column added successfully")
        else:
            print("leverage column already exists")
        
        # Test insert
        print("\nTesting MTF insert...")
        test_data = (
            1,  # user_id
            'buy',  # trade_type
            100.0,  # avg_price
            10,  # quantity
            5.0,  # expected_return
            2.0,  # risk_percent
            250.0,  # capital_used
            105.0,  # target_price
            98.0,  # stop_loss_price
            50.0,  # total_reward
            20.0,  # total_risk
            2.5,  # rr_ratio
            'TESTSTOCK',  # symbol
            'Test MTF trade',  # comment
            'open',  # status
            '2025-01-10 10:00:00',  # timestamp
            4.0  # leverage
        )
        
        cursor.execute("""
            INSERT INTO mtf_trades (
                user_id, trade_type, avg_price, quantity, expected_return, 
                risk_percent, capital_used, target_price, stop_loss_price, 
                total_reward, total_risk, rr_ratio, symbol, comment, 
                status, timestamp, leverage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, test_data)
        
        conn.commit()
        print("Test insert successful!")
        
        # Verify the insert
        cursor.execute("SELECT * FROM mtf_trades WHERE symbol = 'TESTSTOCK' ORDER BY id DESC LIMIT 1")
        record = cursor.fetchone()
        print(f"Inserted record ID: {record[0] if record else 'None'}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    print("MTF Database Fix Script")
    print("=" * 30)
    
    db_path = find_database()
    if not db_path:
        print("Cannot proceed without database file")
        return
    
    success = check_and_fix_mtf_table(db_path)
    
    if success:
        print("\nMTF database schema fixed successfully!")
        print("You can now try saving MTF trades again.")
    else:
        print("\nFailed to fix MTF database schema")

if __name__ == "__main__":
    main()