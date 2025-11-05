#!/usr/bin/env python3
"""
Migration script to add mentor attribution to coupon system
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text

def migrate_mentor_coupons():
    """Add mentor attribution fields to coupon system"""
    
    with app.app_context():
        try:
            print("Starting mentor-coupon migration...")
            
            inspector = db.inspect(db.engine)
            
            # Add mentor_id to coupons table
            coupon_columns = [col['name'] for col in inspector.get_columns('coupon')]
            if 'mentor_id' not in coupon_columns:
                print("Adding mentor_id to coupons table...")
                db.session.execute(text("ALTER TABLE coupon ADD COLUMN mentor_id INTEGER"))
                db.session.execute(text("ALTER TABLE coupon ADD COLUMN mentor_commission_pct REAL DEFAULT 10.0"))
                db.session.execute(text("ALTER TABLE coupon ADD COLUMN max_uses INTEGER DEFAULT 100"))
                db.session.execute(text("ALTER TABLE coupon ADD COLUMN uses INTEGER DEFAULT 0"))
            
            # Update coupon_usage table structure
            usage_columns = [col['name'] for col in inspector.get_columns('coupon_usage')]
            if 'coupon_id' not in usage_columns:
                print("Updating coupon_usage table...")
                db.session.execute(text("ALTER TABLE coupon_usage ADD COLUMN coupon_id INTEGER"))
                db.session.execute(text("ALTER TABLE coupon_usage ADD COLUMN mentor_id INTEGER"))
                db.session.execute(text("ALTER TABLE coupon_usage ADD COLUMN commission_amount INTEGER DEFAULT 0"))
                db.session.execute(text("ALTER TABLE coupon_usage ADD COLUMN order_id VARCHAR(100)"))
            
            db.session.commit()
            print("Mentor-coupon migration completed successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"Migration failed: {e}")
            raise

if __name__ == "__main__":
    migrate_mentor_coupons()