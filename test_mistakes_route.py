#!/usr/bin/env python3
"""
Test the mistakes route to ensure it works after the database fixes.
"""

import os
import sys
from sqlalchemy import create_engine, text

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database_config import get_postgres_url

def test_mistakes_query():
    """Test the query that was failing in the mistakes route"""
    
    engine = create_engine(get_postgres_url())
    
    with engine.connect() as conn:
        try:
            print("Testing mistakes table queries...")
            
            # Test basic select
            result = conn.execute(text("SELECT COUNT(*) FROM mistakes;"))
            count = result.scalar()
            print(f"  Total mistakes: {count}")
            
            # Test the specific query from the route
            result = conn.execute(text("""
                SELECT id, title, description, category, severity, 
                       confidence, pnl_impact, risk_at_time, recurrence_count,
                       created_at, resolved_at
                FROM mistakes 
                ORDER BY created_at DESC 
                LIMIT 5;
            """))
            
            rows = result.fetchall()
            print(f"  Retrieved {len(rows)} sample records")
            
            for row in rows:
                print(f"    ID: {row[0]}, Title: {row[1][:50]}...")
            
            # Test insert (to make sure types work)
            print("\n  Testing insert...")
            conn.execute(text("""
                INSERT INTO mistakes (title, description, category, severity, confidence, pnl_impact, risk_at_time, recurrence_count)
                VALUES ('Test Mistake', 'Test description', 'execution', 'medium', 75, -150.50, 1000.00, 1);
            """))
            
            # Get the inserted record
            result = conn.execute(text("""
                SELECT id, title, confidence, pnl_impact, risk_at_time 
                FROM mistakes 
                WHERE title = 'Test Mistake';
            """))
            
            row = result.fetchone()
            if row:
                print(f"    Inserted record: ID={row[0]}, Confidence={row[2]}, PnL={row[3]}, Risk={row[4]}")
                
                # Clean up test record
                conn.execute(text("DELETE FROM mistakes WHERE title = 'Test Mistake';"))
                print("    Test record cleaned up")
            
            conn.commit()
            print("\nAll tests passed! The mistakes table is working correctly.")
            return True
            
        except Exception as e:
            print(f"\nTest failed: {e}")
            conn.rollback()
            return False

if __name__ == "__main__":
    print("Testing mistakes table functionality...")
    
    if test_mistakes_query():
        print("\nSuccess! The mistakes route should now work properly.")
    else:
        print("\nTests failed. There may still be issues.")
        sys.exit(1)