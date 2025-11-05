#!/usr/bin/env python3
"""
Script to create all essential tables for the mentor payment system
"""

import sqlite3
import os
from datetime import datetime

def create_essential_tables():
    """Create all essential tables"""
    
    # Database path
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'database.db')
    
    # Create instance directory if it doesn't exist
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create mentor table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mentor (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mentor_id VARCHAR(20) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                created_by_admin_id INTEGER,
                active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create coupon table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coupon (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code VARCHAR(50) UNIQUE NOT NULL,
                discount_percent INTEGER NOT NULL,
                created_by VARCHAR(80) NOT NULL,
                active BOOLEAN DEFAULT 1,
                mentor_id INTEGER,
                max_uses INTEGER DEFAULT 100,
                uses INTEGER DEFAULT 0,
                mentor_commission_pct DECIMAL(5,2) DEFAULT 10.0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (mentor_id) REFERENCES mentor (id)
            )
        """)
        
        # Create users table (basic structure)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(100) UNIQUE NOT NULL,
                name VARCHAR(100),
                password_hash VARCHAR(255),
                verified BOOLEAN DEFAULT 0,
                google_id VARCHAR(100),
                subscription_active BOOLEAN DEFAULT 0,
                subscription_type VARCHAR(20),
                subscription_expires DATETIME,
                registered_on DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create coupon_usage table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coupon_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                coupon_id INTEGER NOT NULL,
                coupon_code VARCHAR(50) NOT NULL,
                mentor_id INTEGER,
                payment_id INTEGER,
                discount_amount INTEGER NOT NULL,
                commission_amount INTEGER DEFAULT 0,
                order_id VARCHAR(100),
                used_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (coupon_id) REFERENCES coupon (id),
                FOREIGN KEY (mentor_id) REFERENCES mentor (id)
            )
        """)
        
        # Create indexes for better performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_mentor_email ON mentor(email)",
            "CREATE INDEX IF NOT EXISTS idx_mentor_mentor_id ON mentor(mentor_id)",
            "CREATE INDEX IF NOT EXISTS idx_coupon_code ON coupon(code)",
            "CREATE INDEX IF NOT EXISTS idx_coupon_mentor_id ON coupon(mentor_id)",
            "CREATE INDEX IF NOT EXISTS idx_coupon_usage_user_id ON coupon_usage(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_coupon_usage_mentor_id ON coupon_usage(mentor_id)",
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        conn.commit()
        print("All essential tables created successfully!")
        
        # Show all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"\nCreated tables: {tables}")
        
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
    print("Creating essential tables...")
    success = create_essential_tables()
    if success:
        print("All tables created successfully!")
    else:
        print("Table creation failed!")