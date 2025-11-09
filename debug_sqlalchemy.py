#!/usr/bin/env python3
"""
Debug SQLAlchemy structure to find the correct method to patch
"""

def debug_sqlalchemy_structure():
    """Debug the SQLAlchemy PostgreSQL dialect structure"""
    try:
        from sqlalchemy.dialects.postgresql import psycopg2
        
        print("PGDialect_psycopg2 attributes:")
        for attr in dir(psycopg2.PGDialect_psycopg2):
            if 'result' in attr.lower() or 'process' in attr.lower():
                print(f"  {attr}")
        
        print("\nChecking for result_processor method:")
        if hasattr(psycopg2.PGDialect_psycopg2, 'result_processor'):
            print("  result_processor: EXISTS")
        else:
            print("  result_processor: NOT FOUND")
            
        print("\nChecking parent classes:")
        for cls in psycopg2.PGDialect_psycopg2.__mro__:
            print(f"  {cls}")
            if hasattr(cls, 'result_processor'):
                print(f"    -> has result_processor")
        
        # Check the actual error location
        print("\nTrying to trigger the error to see where it comes from...")
        try:
            from sqlalchemy import create_engine
            from database_config import get_postgres_url
            
            engine = create_engine(get_postgres_url())
            with engine.connect() as conn:
                result = conn.execute("SELECT 'test'::varchar as test_col")
                row = result.fetchone()
                print(f"Query succeeded: {row}")
        except Exception as e:
            print(f"Error occurred: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"Debug failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_sqlalchemy_structure()