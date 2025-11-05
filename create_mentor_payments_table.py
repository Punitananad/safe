#!/usr/bin/env python3
"""
Script to create mentor_payments table with all required fields
"""

import sqlite3
import os
from datetime import datetime

def create_mentor_payments_table():
    """Create mentor_payments table with all required fields"""
    
    # Database path
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'database.db')
    
    # Create instance directory if it doesn't exist
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create mentor_payments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mentor_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mentor_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                payment_date DATETIME NOT NULL,
                payment_method VARCHAR(50) DEFAULT 'Manual',
                reference_number VARCHAR(100),
                period_start VARCHAR(50),
                period_end VARCHAR(50),
                commission_count INTEGER DEFAULT 0,
                notes TEXT,
                paid_by VARCHAR(50) DEFAULT 'admin',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (mentor_id) REFERENCES mentor (id)
            )
        """)
        
        # Create index for better performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_mentor_payments_mentor_id 
            ON mentor_payments(mentor_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_mentor_payments_payment_date 
            ON mentor_payments(payment_date)
        """)
        
        conn.commit()
        print("mentor_payments table created successfully!")
        
        # Show table structure
        cursor.execute("PRAGMA table_info(mentor_payments)")
        columns = cursor.fetchall()
        print("\nTable structure:")
        for col in columns:
            print(f"  {col[1]} {col[2]} {'NOT NULL' if col[3] else 'NULL'} {'DEFAULT ' + str(col[4]) if col[4] else ''}")
        
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Creating mentor_payments table...")
    success = create_mentor_payments_table()
    if success:
        print("Table creation completed successfully!")
    else:
        print("Table creation failed!")