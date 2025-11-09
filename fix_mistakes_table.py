#!/usr/bin/env python3
"""
Fix mistakes table schema and data type issues for PostgreSQL compatibility.
This script addresses the OID 1043 (VARCHAR) vs numeric type mismatch error.
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database_config import get_postgres_url

def fix_mistakes_table():
    """Fix the mistakes table schema to ensure proper data types"""
    
    engine = create_engine(get_postgres_url())
    
    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()
        
        try:
            print("Checking mistakes table schema...")
            
            # Check current column types
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'mistakes' 
                ORDER BY ordinal_position;
            """))
            
            columns = result.fetchall()
            print(f"Found {len(columns)} columns in mistakes table:")
            for col in columns:
                print(f"  - {col[0]}: {col[1]} ({'NULL' if col[2] == 'YES' else 'NOT NULL'})")
            
            # Check for problematic data in numeric fields
            print("\nChecking for invalid data in numeric fields...")
            
            numeric_fields = ['pnl_impact', 'risk_at_time', 'confidence', 'recurrence_count', 'time_to_resolve_seconds']
            
            for field in numeric_fields:
                try:
                    # Check if column exists
                    col_exists = any(col[0] == field for col in columns)
                    if not col_exists:
                        print(f"  WARNING: Column {field} does not exist, skipping...")
                        continue
                    
                    # Find non-numeric values
                    result = conn.execute(text(f"""
                        SELECT id, {field} 
                        FROM mistakes 
                        WHERE {field} IS NOT NULL 
                        AND {field}::text !~ '^-?[0-9]*[.]?[0-9]*$'
                        LIMIT 5;
                    """))
                    
                    bad_rows = result.fetchall()
                    if bad_rows:
                        print(f"  ERROR: Found {len(bad_rows)} invalid values in {field}:")
                        for row in bad_rows:
                            print(f"    ID {row[0]}: '{row[1]}'")
                    else:
                        print(f"  OK: {field} - all values are valid")
                        
                except Exception as e:
                    print(f"  WARNING: Error checking {field}: {e}")
            
            # Fix data types if needed
            print("\nFixing data types...")
            
            # Clean up invalid data first
            print("  Cleaning invalid data...")
            
            # Set empty strings and invalid values to NULL for numeric fields
            for field in numeric_fields:
                try:
                    col_exists = any(col[0] == field for col in columns)
                    if not col_exists:
                        continue
                        
                    conn.execute(text(f"""
                        UPDATE mistakes 
                        SET {field} = NULL 
                        WHERE {field} IS NOT NULL 
                        AND ({field}::text = '' OR {field}::text !~ '^-?[0-9]*[.]?[0-9]*$');
                    """))
                    print(f"    OK: Cleaned {field}")
                except Exception as e:
                    print(f"    WARNING: Error cleaning {field}: {e}")
            
            # Now fix the column types
            print("  Updating column types...")
            
            # Map of columns to their correct types
            type_fixes = {
                'pnl_impact': 'NUMERIC(18,2)',
                'risk_at_time': 'NUMERIC(18,2)', 
                'confidence': 'INTEGER',
                'recurrence_count': 'INTEGER',
                'time_to_resolve_seconds': 'INTEGER',
                'attachments_count': 'INTEGER'
            }
            
            for field, new_type in type_fixes.items():
                try:
                    col_exists = any(col[0] == field for col in columns)
                    if not col_exists:
                        print(f"    WARNING: Column {field} does not exist, skipping...")
                        continue
                    
                    # Check current type
                    current_type = next((col[1] for col in columns if col[0] == field), None)
                    
                    if current_type and 'varchar' in current_type.lower():
                        print(f"    Converting {field} from {current_type} to {new_type}")
                        
                        # Use USING clause to handle conversion
                        if 'INTEGER' in new_type:
                            conn.execute(text(f"""
                                ALTER TABLE mistakes 
                                ALTER COLUMN {field} TYPE {new_type} 
                                USING CASE 
                                    WHEN {field} IS NULL OR {field}::text = '' THEN NULL
                                    ELSE {field}::INTEGER 
                                END;
                            """))
                        else:  # NUMERIC
                            conn.execute(text(f"""
                                ALTER TABLE mistakes 
                                ALTER COLUMN {field} TYPE {new_type} 
                                USING CASE 
                                    WHEN {field} IS NULL OR {field}::text = '' THEN NULL
                                    ELSE {field}::NUMERIC 
                                END;
                            """))
                        
                        print(f"    OK: Successfully converted {field}")
                    else:
                        print(f"    OK: {field} already has correct type ({current_type})")
                        
                except Exception as e:
                    print(f"    ERROR: Error converting {field}: {e}")
            
            # Commit transaction
            trans.commit()
            print("\nSuccessfully fixed mistakes table schema!")
            
        except Exception as e:
            # Rollback on error
            trans.rollback()
            print(f"\nError fixing mistakes table: {e}")
            raise
            
def verify_fix():
    """Verify that the fix worked"""
    engine = create_engine(get_postgres_url())
    
    with engine.connect() as conn:
        try:
            print("\nVerifying fix...")
            
            # Check final column types
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'mistakes' 
                AND column_name IN ('pnl_impact', 'risk_at_time', 'confidence', 'recurrence_count', 'time_to_resolve_seconds', 'attachments_count')
                ORDER BY column_name;
            """))
            
            columns = result.fetchall()
            print("Final column types:")
            for col in columns:
                print(f"  - {col[0]}: {col[1]}")
            
            # Test a simple query that was failing before
            result = conn.execute(text("SELECT COUNT(*) FROM mistakes;"))
            count = result.scalar()
            print(f"\nSuccessfully queried mistakes table: {count} records")
            
            # Test the specific query that was failing
            result = conn.execute(text("""
                SELECT id, title, pnl_impact, confidence 
                FROM mistakes 
                LIMIT 1;
            """))
            
            row = result.fetchone()
            if row:
                print(f"Sample record: ID={row[0]}, Title='{row[1]}', PnL Impact={row[2]}, Confidence={row[3]}")
            else:
                print("No records found, but query executed successfully")
                
        except Exception as e:
            print(f"Verification failed: {e}")
            return False
    
    return True

if __name__ == "__main__":
    print("Starting mistakes table fix...")
    
    try:
        fix_mistakes_table()
        
        if verify_fix():
            print("\nAll fixes completed successfully!")
            print("The mistakes table should now work properly with PostgreSQL.")
        else:
            print("\nFix completed but verification failed.")
            
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)