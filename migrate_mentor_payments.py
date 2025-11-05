#!/usr/bin/env python3
"""
Migration script to add mentor payment tracking table
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text

def migrate_mentor_payments():
    """Add mentor payment tracking table"""
    
    with app.app_context():
        try:
            print("Creating mentor_payments table...")
            
            # Create mentor_payments table
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS mentor_payments (
                    id INTEGER PRIMARY KEY,
                    mentor_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    payment_date DATETIME NOT NULL,
                    payment_method VARCHAR(50) DEFAULT 'Manual',
                    reference_number VARCHAR(100),
                    period_start DATE,
                    period_end DATE,
                    commission_count INTEGER DEFAULT 0,
                    notes TEXT,
                    paid_by VARCHAR(100) DEFAULT 'admin',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            db.session.commit()
            print("Mentor payments table created successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"Migration failed: {e}")
            raise

if __name__ == "__main__":
    migrate_mentor_payments()