#!/usr/bin/env python3
"""
Add leverage column to mtf_trades table
"""

from app import app, db
from sqlalchemy import text

def add_mtf_leverage_column():
    """Add leverage column to mtf_trades table"""
    with app.app_context():
        try:
            # Check if column already exists
            result = db.session.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'mtf_trades' AND column_name = 'leverage'
                """)
            ).fetchone()
            
            if result:
                print("✓ leverage column already exists in mtf_trades table")
                return True
            
            # Add the leverage column
            db.session.execute(
                text("ALTER TABLE mtf_trades ADD COLUMN leverage FLOAT DEFAULT 4.0")
            )
            db.session.commit()
            print("✓ Added leverage column to mtf_trades table")
            return True
            
        except Exception as e:
            print(f"✗ Error adding leverage column: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    print("Adding leverage column to MTF trades table...")
    success = add_mtf_leverage_column()
    if success:
        print("🎉 Migration completed successfully!")
    else:
        print("⚠️ Migration failed")