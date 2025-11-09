"""
Symbol utilities for fetching symbols from dhan_symbols.db
"""
import sqlite3
import os

def get_db_connection():
    """Get database connection to dhan_symbols.db"""
    db_path = os.path.join('instance', 'dhan_symbols.db')
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")
    return sqlite3.connect(db_path)

def search_symbols(query, limit=10):
    """
    Search for symbols in the database
    
    Args:
        query (str): Search query
        limit (int): Maximum number of results
    
    Returns:
        list: List of symbol dictionaries
    """
    if not query:
        return []
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        q_upper = query.upper()
        search_pattern = f"%{q_upper}%"
        
        cursor.execute("""
        SELECT
            SYMBOL_NAME,
            DISPLAY_NAME,
            SECURITY_ID,
            CASE
                WHEN UPPER(SYMBOL_NAME) = ? THEN 300
                WHEN UPPER(DISPLAY_NAME) = ? THEN 250
                WHEN UPPER(SYMBOL_NAME) LIKE ? THEN 200
                WHEN UPPER(DISPLAY_NAME) LIKE ? THEN 100
                WHEN UPPER(SYMBOL_NAME) LIKE ? THEN 80
                WHEN UPPER(DISPLAY_NAME) LIKE ? THEN 50
                ELSE 0
            END AS score
        FROM instruments
        WHERE SEGMENT = 'E' AND EXCH_ID = 'NSE'
          AND (
            UPPER(SYMBOL_NAME) LIKE ?
            OR UPPER(DISPLAY_NAME) LIKE ?
          )
        ORDER BY score DESC, LENGTH(SYMBOL_NAME) ASC, SYMBOL_NAME ASC
        LIMIT ?
        """, (q_upper, q_upper, f"{q_upper}%", f"{q_upper}%", 
              search_pattern, search_pattern, search_pattern, search_pattern, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'symbol': row[0],
                'name': row[1] or row[0],
                'security_id': int(row[2]),
                'score': row[3]
            }
            for row in rows
        ]
        
    except Exception as e:
        print(f"Error searching symbols: {e}")
        return []

def resolve_symbol(symbol_name):
    """
    Resolve a symbol to get its details
    
    Args:
        symbol_name (str): Symbol name to resolve
    
    Returns:
        dict or None: Symbol details if found
    """
    if not symbol_name:
        return None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Try exact match first
        cursor.execute("""
            SELECT SYMBOL_NAME, DISPLAY_NAME, SECURITY_ID, EXCH_ID, SEGMENT
            FROM instruments
            WHERE EXCH_ID='NSE' AND SEGMENT='E' AND UPPER(SYMBOL_NAME)=?
            LIMIT 1
        """, (symbol_name.upper(),))
        
        result = cursor.fetchone()
        
        # If not found, try display name match
        if not result:
            cursor.execute("""
                SELECT SYMBOL_NAME, DISPLAY_NAME, SECURITY_ID, EXCH_ID, SEGMENT
                FROM instruments
                WHERE EXCH_ID='NSE' AND SEGMENT='E' AND UPPER(DISPLAY_NAME)=?
                LIMIT 1
            """, (symbol_name.upper(),))
            result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return {
                'symbol': result[0],
                'display_name': result[1],
                'security_id': int(result[2]),
                'exchange': result[3],
                'segment': result[4]
            }
        
        return None
        
    except Exception as e:
        print(f"Error resolving symbol: {e}")
        return None

def get_symbol_by_id(security_id):
    """
    Get symbol details by security ID
    
    Args:
        security_id (int): Security ID
    
    Returns:
        dict or None: Symbol details if found
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT SYMBOL_NAME, DISPLAY_NAME, SECURITY_ID, EXCH_ID, SEGMENT
            FROM instruments
            WHERE SECURITY_ID=? AND EXCH_ID='NSE' AND SEGMENT='E'
            LIMIT 1
        """, (str(security_id),))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'symbol': result[0],
                'display_name': result[1],
                'security_id': int(result[2]),
                'exchange': result[3],
                'segment': result[4]
            }
        
        return None
        
    except Exception as e:
        print(f"Error getting symbol by ID: {e}")
        return None

# Test functions
if __name__ == "__main__":
    print("Testing symbol utilities...")
    
    # Test search
    print("\n1. Searching for 'STATE BANK':")
    results = search_symbols("STATE BANK", 5)
    for result in results:
        print(f"   {result['symbol']} - {result['name']} (ID: {result['security_id']}, Score: {result['score']})")
    
    # Test resolve
    print("\n2. Resolving 'STATE BANK OF INDIA':")
    result = resolve_symbol("STATE BANK OF INDIA")
    if result:
        print(f"   Found: {result}")
    else:
        print("   Not found")
    
    # Test by ID
    print("\n3. Getting symbol by ID 3045:")
    result = get_symbol_by_id(3045)
    if result:
        print(f"   Found: {result}")
    else:
        print("   Not found")