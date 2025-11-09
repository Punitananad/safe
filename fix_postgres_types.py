#!/usr/bin/env python3
"""
Fix PostgreSQL type compatibility issues
"""
import os
import sys

def fix_postgres_types():
    """Apply PostgreSQL type fixes"""
    try:
        # Import required modules
        import psycopg2
        import psycopg2.extensions
        import psycopg2.extras
        from sqlalchemy import create_engine
        from database_config import get_postgres_url
        
        print("Applying PostgreSQL type fixes...")
        
        # Register JSON adapter
        psycopg2.extensions.register_adapter(dict, psycopg2.extras.Json)
        
        # Create a test connection to register types
        engine = create_engine(get_postgres_url())
        with engine.connect() as conn:
            # This will register all PostgreSQL types
            raw_conn = conn.connection.connection
            
            # Register UUID type if available
            try:
                psycopg2.extras.register_uuid(conn_or_curs=raw_conn)
            except:
                pass
                
            # Register hstore if available
            try:
                psycopg2.extras.register_hstore(raw_conn)
            except:
                pass
        
        print("[OK] PostgreSQL types registered successfully!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to register PostgreSQL types: {e}")
        return False

if __name__ == "__main__":
    success = fix_postgres_types()
    if success:
        print("PostgreSQL type fixes applied. You can now run your application.")
    else:
        print("Failed to apply fixes. Check your PostgreSQL installation.")
        sys.exit(1)