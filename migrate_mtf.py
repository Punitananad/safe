#!/usr/bin/env python3
"""
Simple migration to add leverage column to mtf_trades table
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def add_leverage_column():
    """Add leverage column to mtf_trades table"""
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'calculatentrade_db'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD')
        )
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'mtf_trades' AND column_name = 'leverage'
        """)
        
        if cursor.fetchone():
            print("leverage column already exists")
            return True
        
        # Add leverage column
        cursor.execute("ALTER TABLE mtf_trades ADD COLUMN leverage FLOAT DEFAULT 4.0")
        conn.commit()
        
        print("Added leverage column to mtf_trades table")
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    print("Adding leverage column to MTF trades...")
    if add_leverage_column():
        print("Migration successful!")
    else:
        print("Migration failed")