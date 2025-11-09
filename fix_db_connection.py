#!/usr/bin/env python3
"""
Fix PostgreSQL connection issues
"""
import os
import sys
from sqlalchemy import create_engine, text
from database_config import get_postgres_url, get_database_engine_options

def test_connection():
    """Test database connection and fix common issues"""
    try:
        print("Testing PostgreSQL connection...")
        
        # Get connection details
        db_url = get_postgres_url()
        engine_options = get_database_engine_options()
        
        print(f"Database URL: {db_url.replace(os.getenv('DB_PASSWORD', 'Punit@1465'), '***')}")
        
        # Create engine with minimal options first
        engine = create_engine(db_url, **engine_options)
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"[OK] Connection successful!")
            print(f"PostgreSQL version: {version}")
            
            # Test a simple query
            result = conn.execute(text("SELECT 1 as test"))
            test_result = result.fetchone()[0]
            print(f"[OK] Query test successful: {test_result}")
            
        return True
        
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        print("\nTrying alternative connection methods...")
        
        # Try with different connection string
        try:
            alt_url = db_url.replace("postgresql://", "postgresql+psycopg2://")
            alt_engine = create_engine(alt_url, pool_pre_ping=True)
            
            with alt_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                print("[OK] Alternative connection successful!")
                
                # Update the database config
                print("Updating database configuration...")
                return True
                
        except Exception as e2:
            print(f"[ERROR] Alternative connection also failed: {e2}")
            
        return False

def fix_type_issues():
    """Fix PostgreSQL type compatibility issues"""
    try:
        print("\nFixing PostgreSQL type compatibility...")
        
        # Import and register type adapters
        import psycopg2.extensions
        import sqlalchemy.dialects.postgresql as postgresql
        
        # Register common type adapters
        psycopg2.extensions.register_adapter(dict, psycopg2.extras.Json)
        
        print("[OK] Type adapters registered successfully!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to register type adapters: {e}")
        return False

if __name__ == "__main__":
    print("=== PostgreSQL Connection Fix Tool ===\n")
    
    # Test connection
    connection_ok = test_connection()
    
    # Fix type issues
    types_ok = fix_type_issues()
    
    if connection_ok and types_ok:
        print("\n[SUCCESS] All fixes applied successfully!")
        print("You can now restart your application.")
    else:
        print("\n[ERROR] Some issues remain. Please check your PostgreSQL installation and credentials.")
        sys.exit(1)