#!/usr/bin/env python3
"""
Migration script to add missing fields to mentor_payments table
"""

import sqlite3
import os
from datetime import datetime

def migrate_payment_fields():
    """Add missing fields to mentor_payments table"""
    
    # Database path
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'database.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if mentor_payments table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='mentor_payments'
        """)
        
        if not cursor.fetchone():
            print("mentor_payments table not found")
            return False
        
        # Get current table structure
        cursor.execute("PRAGMA table_info(mentor_payments)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Current columns: {columns}")
        
        # Add missing columns if they don't exist
        new_columns = [
            ("commission_count", "INTEGER DEFAULT 0"),
            ("created_at", "DATETIME DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")
        ]
        
        for column_name, column_def in new_columns:
            if column_name not in columns:
                try:
                    cursor.execute(f"ALTER TABLE mentor_payments ADD COLUMN {column_name} {column_def}")
                    print(f"Added column: {column_name}")
                except sqlite3.Error as e:
                    print(f"Error adding column {column_name}: {e}")
        
        # Update existing records to have created_at if null
        cursor.execute("""
            UPDATE mentor_payments 
            SET created_at = payment_date 
            WHERE created_at IS NULL
        """)
        
        conn.commit()
        print("Migration completed successfully!")
        
        # Show final table structure
        cursor.execute("PRAGMA table_info(mentor_payments)")
        final_columns = cursor.fetchall()
        print("\nFinal table structure:")
        for col in final_columns:
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
    print("Starting mentor_payments table migration...")
    success = migrate_payment_fields()
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")