#!/usr/bin/env python3
"""
Migration script to add coupon functionality to the database.
Run this script to add the new columns and table for coupon support.
"""

import os
import sys
from datetime import datetime, timezone

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text

def migrate_coupon_fields():
    """Add coupon-related fields and tables to the database"""
    
    with app.app_context():
        try:
            print("Starting coupon functionality migration...")
            
            # Check if columns already exist
            inspector = db.inspect(db.engine)
            payment_columns = [col['name'] for col in inspector.get_columns('payments')]
            
            # Add new columns to payments table if they don't exist
            if 'original_amount' not in payment_columns:
                print("Adding original_amount column to payments table...")
                db.session.execute(text("ALTER TABLE payments ADD COLUMN original_amount INTEGER NOT NULL DEFAULT 0"))
            
            if 'discount_amount' not in payment_columns:
                print("Adding discount_amount column to payments table...")
                db.session.execute(text("ALTER TABLE payments ADD COLUMN discount_amount INTEGER NOT NULL DEFAULT 0"))
            
            if 'coupon_code' not in payment_columns:
                print("Adding coupon_code column to payments table...")
                db.session.execute(text("ALTER TABLE payments ADD COLUMN coupon_code VARCHAR(50)"))
            
            # Update existing payments to have original_amount = amount
            print("Updating existing payment records...")
            db.session.execute(text("UPDATE payments SET original_amount = amount WHERE original_amount = 0"))
            
            # Create coupon_usage table if it doesn't exist
            existing_tables = inspector.get_table_names()
            if 'coupon_usage' not in existing_tables:
                print("Creating coupon_usage table...")
                db.session.execute(text("""
                    CREATE TABLE coupon_usage (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        coupon_code VARCHAR(50) NOT NULL,
                        payment_id INTEGER,
                        discount_amount INTEGER NOT NULL,
                        used_at DATETIME NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users (id),
                        FOREIGN KEY (payment_id) REFERENCES payments (id)
                    )
                """))
            
            db.session.commit()
            print("✅ Coupon functionality migration completed successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {e}")
            raise

if __name__ == "__main__":
    migrate_coupon_fields()