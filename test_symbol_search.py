#!/usr/bin/env python3
"""
Test the symbol search functionality after migration
"""

from sqlalchemy import create_engine, text
from database_config import get_postgres_url

def test_symbol_search():
    """Test symbol search functionality"""
    try:
        engine = create_engine(get_postgres_url())
        
        with engine.connect() as conn:
            # Test basic count
            result = conn.execute(text("SELECT COUNT(*) FROM instruments")).fetchone()
            print(f"[INFO] Total symbols in database: {result[0]}")
            
            # Test search for common symbols
            test_queries = ['HDFC', 'SBIN', 'TCS', 'RELIANCE', 'INFY', 'BANK']
            
            for query in test_queries:
                print(f"\n[TEST] Searching for '{query}':")
                
                search_pattern = f"%{query.upper()}%"
                rows = conn.execute(text("""
                    SELECT symbol_name, display_name, security_id
                    FROM instruments
                    WHERE exch_id = 'NSE' AND segment = 'E'
                      AND (UPPER(symbol_name) LIKE :pattern OR UPPER(display_name) LIKE :pattern)
                    ORDER BY 
                        CASE
                            WHEN UPPER(symbol_name) = :query THEN 1
                            WHEN UPPER(symbol_name) LIKE :query_prefix THEN 2
                            ELSE 3
                        END,
                        LENGTH(symbol_name)
                    LIMIT 5
                """), {
                    'pattern': search_pattern,
                    'query': query.upper(),
                    'query_prefix': f"{query.upper()}%"
                }).fetchall()
                
                if rows:
                    for row in rows:
                        print(f"  {row[0]} | {row[1]} | {row[2]}")
                else:
                    print(f"  No results found for '{query}'")
            
            # Test specific symbols that should exist
            print(f"\n[TEST] Testing specific symbol lookups:")
            specific_symbols = ['HDFCBANK', 'SBIN', 'TCS', 'RELIANCE', 'INFY']
            
            for symbol in specific_symbols:
                result = conn.execute(text("""
                    SELECT symbol_name, display_name, security_id
                    FROM instruments
                    WHERE exch_id = 'NSE' AND segment = 'E' AND UPPER(symbol_name) = :symbol
                """), {'symbol': symbol.upper()}).fetchone()
                
                if result:
                    print(f"  [FOUND] {symbol}: {result[0]} | {result[1]} | {result[2]}")
                else:
                    print(f"  [NOT FOUND] {symbol}: Not found")
            
            # Show some random samples
            print(f"\n[INFO] Random sample of symbols:")
            samples = conn.execute(text("""
                SELECT symbol_name, display_name, security_id
                FROM instruments
                WHERE exch_id = 'NSE' AND segment = 'E'
                  AND symbol_name IS NOT NULL
                  AND LENGTH(symbol_name) BETWEEN 3 AND 15
                ORDER BY RANDOM()
                LIMIT 10
            """)).fetchall()
            
            for row in samples:
                print(f"  {row[0]} | {row[1]} | {row[2]}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing symbol search functionality...")
    success = test_symbol_search()
    if success:
        print("\n[SUCCESS] Symbol search test completed!")
    else:
        print("\n[ERROR] Symbol search test failed!")