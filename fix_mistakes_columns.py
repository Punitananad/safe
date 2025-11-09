#!/usr/bin/env python3
"""
Fix specific columns in mistakes table that are causing type mismatch errors.
"""

import os
import sys
from sqlalchemy import create_engine, text

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database_config import get_postgres_url

def fix_specific_columns():
    """Fix the specific columns causing issues"""
    
    engine = create_engine(get_postgres_url())
    
    with engine.connect() as conn:
        trans = conn.begin()
        
        try:
            print("Fixing specific columns in mistakes table...")
            
            # Fix confidence column (should be INTEGER)
            print("  Converting confidence from VARCHAR to INTEGER...")
            conn.execute(text("""
                ALTER TABLE mistakes 
                ALTER COLUMN confidence TYPE INTEGER 
                USING CASE 
                    WHEN confidence IS NULL OR confidence = '' THEN NULL
                    WHEN confidence ~ '^[0-9]+$' THEN confidence::INTEGER
                    ELSE NULL 
                END;
            """))
            print("    OK: confidence converted to INTEGER")
            
            # Fix risk_at_time column (should be NUMERIC)
            print("  Converting risk_at_time from VARCHAR to NUMERIC...")
            conn.execute(text("""
                ALTER TABLE mistakes 
                ALTER COLUMN risk_at_time TYPE NUMERIC(18,2) 
                USING CASE 
                    WHEN risk_at_time IS NULL OR risk_at_time = '' THEN NULL
                    WHEN risk_at_time ~ '^-?[0-9]*[.]?[0-9]*$' THEN risk_at_time::NUMERIC
                    ELSE NULL 
                END;
            """))
            print("    OK: risk_at_time converted to NUMERIC(18,2)")
            
            trans.commit()
            print("\nSuccessfully fixed column types!")
            
        except Exception as e:
            trans.rollback()
            print(f"\nError fixing columns: {e}")
            raise

def verify_columns():
    """Verify the column types are correct"""
    engine = create_engine(get_postgres_url())
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'mistakes' 
            AND column_name IN ('confidence', 'risk_at_time')
            ORDER BY column_name;
        """))
        
        columns = result.fetchall()
        print("\nVerified column types:")
        for col in columns:
            print(f"  - {col[0]}: {col[1]}")
        
        # Test the query that was failing
        try:
            result = conn.execute(text("""
                SELECT id, confidence, risk_at_time 
                FROM mistakes 
                LIMIT 1;
            """))
            print("\nTest query executed successfully!")
            return True
        except Exception as e:
            print(f"\nTest query failed: {e}")
            return False

if __name__ == "__main__":
    print("Starting column type fixes...")
    
    try:
        fix_specific_columns()
        
        if verify_columns():
            print("\nAll column fixes completed successfully!")
        else:
            print("\nColumn fixes completed but verification failed.")
            
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)