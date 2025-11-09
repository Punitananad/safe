import sqlite3
import os

def get_symbols_from_db(search_query="", limit=50):
    """
    Fetch symbols from dhan_symbols.db based on search query
    
    Args:
        search_query (str): Search term to filter symbols
        limit (int): Maximum number of results to return
    
    Returns:
        list: List of dictionaries containing symbol data
    """
    db_path = os.path.join('instance', 'dhan_symbols.db')
    
    if not os.path.exists(db_path):
        return []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        if search_query:
            # Search in both symbol_name and display_name
            query = """
            SELECT SYMBOL_NAME, DISPLAY_NAME, SECURITY_ID, EXCH_ID, SEGMENT
            FROM instruments 
            WHERE (UPPER(SYMBOL_NAME) LIKE UPPER(?) 
                   OR UPPER(DISPLAY_NAME) LIKE UPPER(?))
                   AND EXCH_ID = 'NSE' 
                   AND SEGMENT = 'E'
            ORDER BY 
                CASE 
                    WHEN UPPER(SYMBOL_NAME) = UPPER(?) THEN 1
                    WHEN UPPER(SYMBOL_NAME) LIKE UPPER(?) THEN 2
                    WHEN UPPER(DISPLAY_NAME) LIKE UPPER(?) THEN 3
                    ELSE 4
                END,
                LENGTH(SYMBOL_NAME),
                SYMBOL_NAME
            LIMIT ?
            """
            search_pattern = f"%{search_query}%"
            cursor.execute(query, (search_pattern, search_pattern, search_query, 
                                 f"{search_query}%", f"{search_query}%", limit))
        else:
            # Get all NSE equity symbols
            query = """
            SELECT SYMBOL_NAME, DISPLAY_NAME, SECURITY_ID, EXCH_ID, SEGMENT
            FROM instruments 
            WHERE EXCH_ID = 'NSE' AND SEGMENT = 'E'
            ORDER BY SYMBOL_NAME
            LIMIT ?
            """
            cursor.execute(query, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        symbols = []
        for row in rows:
            symbols.append({
                'symbol': row[0],
                'name': row[1] or row[0],
                'security_id': row[2],
                'exchange': row[3],
                'segment': row[4]
            })
        
        return symbols
        
    except Exception as e:
        print(f"Error fetching symbols: {e}")
        return []

def search_symbol(symbol_name):
    """
    Search for a specific symbol
    
    Args:
        symbol_name (str): Symbol to search for
    
    Returns:
        dict or None: Symbol data if found
    """
    symbols = get_symbols_from_db(symbol_name, 1)
    return symbols[0] if symbols else None

if __name__ == "__main__":
    # Test the functions
    print("Testing symbol search...")
    
    # Search for SBIN
    result = search_symbol("SBIN")
    print(f"SBIN search result: {result}")
    
    # Search for symbols containing "BANK"
    bank_symbols = get_symbols_from_db("BANK", 10)
    print(f"\nBank symbols (first 10):")
    for symbol in bank_symbols:
        print(f"  {symbol['symbol']} - {symbol['name']}")