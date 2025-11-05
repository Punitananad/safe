#!/usr/bin/env python3
"""
Database migration script to add commission_pct column to mentor table
"""
import sqlite3
import os

def migrate_database():
    # Path to the database
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'calculatentrade.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if commission_pct column exists
        cursor.execute("PRAGMA table_info(mentor)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'commission_pct' not in columns:
            print("Adding commission_pct column to mentor table...")
            cursor.execute("ALTER TABLE mentor ADD COLUMN commission_pct REAL DEFAULT 40.0")
            conn.commit()
            print("Successfully added commission_pct column with default value 40.0")
        else:
            print("commission_pct column already exists")
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(mentor)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"Current mentor table columns: {columns}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        return False

if __name__ == "__main__":
    print("Starting database migration...")
    success = migrate_database()
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")