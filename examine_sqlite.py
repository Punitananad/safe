#!/usr/bin/env python3
"""
Examine the all_symbol.db SQLite database to understand its structure
"""

import sqlite3

def examine_sqlite():
    """Examine the SQLite database in detail"""
    try:
        conn = sqlite3.connect('all_symbol.db')
        cursor = conn.cursor()
        
        # Get unique exchange values
        cursor.execute("SELECT DISTINCT EXCH_ID FROM instruments ORDER BY EXCH_ID;")
        exchanges = cursor.fetchall()
        print(f"[INFO] Unique exchanges: {[ex[0] for ex in exchanges]}")
        
        # Get unique segment values
        cursor.execute("SELECT DISTINCT SEGMENT FROM instruments ORDER BY SEGMENT;")
        segments = cursor.fetchall()
        print(f"[INFO] Unique segments: {[seg[0] for seg in segments]}")
        
        # Get count by exchange
        cursor.execute("SELECT EXCH_ID, COUNT(*) FROM instruments GROUP BY EXCH_ID ORDER BY COUNT(*) DESC;")
        exchange_counts = cursor.fetchall()
        print(f"[INFO] Records by exchange:")
        for ex, count in exchange_counts:
            print(f"  {ex}: {count}")
        
        # Get count by segment
        cursor.execute("SELECT SEGMENT, COUNT(*) FROM instruments GROUP BY SEGMENT ORDER BY COUNT(*) DESC;")
        segment_counts = cursor.fetchall()
        print(f"[INFO] Records by segment:")
        for seg, count in segment_counts:
            print(f"  {seg}: {count}")
        
        # Get NSE records by segment
        cursor.execute("SELECT SEGMENT, COUNT(*) FROM instruments WHERE EXCH_ID = 'NSE' GROUP BY SEGMENT ORDER BY COUNT(*) DESC;")
        nse_segments = cursor.fetchall()
        print(f"[INFO] NSE records by segment:")
        for seg, count in nse_segments:
            print(f"  {seg}: {count}")
        
        # Get sample NSE equity records
        cursor.execute("SELECT * FROM instruments WHERE EXCH_ID = 'NSE' LIMIT 10;")
        nse_samples = cursor.fetchall()
        print(f"[INFO] Sample NSE records:")
        for record in nse_samples:
            print(f"  {record}")
        
        conn.close()
        
    except Exception as e:
        print(f"[ERROR] Error examining SQLite database: {e}")

if __name__ == "__main__":
    examine_sqlite()