#!/usr/bin/env python3
"""
Migrate all_symbol.db SQLite database to PostgreSQL instruments table
"""

import os
import sys
import sqlite3
from sqlalchemy import create_engine, text
from database_config import get_postgres_url

def examine_sqlite_structure():
    """Examine the structure of all_symbol.db"""
    try:
        conn = sqlite3.connect('all_symbol.db')
        cursor = conn.cursor()
        
        # Get table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"[INFO] Found tables: {[table[0] for table in tables]}")
        
        for table_name in [table[0] for table in tables]:
            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            print(f"\n[INFO] Table '{table_name}' columns:")
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")
            
            # Get sample data
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
            sample_data = cursor.fetchall()
            print(f"[INFO] Sample data from '{table_name}':")
            for row in sample_data:
                print(f"  {row}")
            
            # Get total count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"[INFO] Total records in '{table_name}': {count}")
        
        conn.close()
        return tables
        
    except Exception as e:
        print(f"[ERROR] Error examining SQLite database: {e}")
        return []

def migrate_symbols_to_postgres():
    """Migrate symbols from SQLite to PostgreSQL"""
    try:
        # First examine the SQLite structure
        print("Examining SQLite database structure...")
        tables = examine_sqlite_structure()
        
        if not tables:
            print("[ERROR] No tables found in SQLite database")
            return False
        
        # Connect to SQLite
        sqlite_conn = sqlite3.connect('all_symbol.db')
        sqlite_cursor = sqlite_conn.cursor()
        
        # Connect to PostgreSQL
        pg_engine = create_engine(get_postgres_url())
        
        with pg_engine.connect() as pg_conn:
            # Clear existing instruments table
            print("[INFO] Clearing existing instruments table...")
            pg_conn.execute(text("DELETE FROM instruments"))
            
            # Find the main symbols table (usually the largest one)
            main_table = None
            max_count = 0
            
            for table_name in [table[0] for table in tables]:
                sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = sqlite_cursor.fetchone()[0]
                if count > max_count:
                    max_count = count
                    main_table = table_name
            
            print(f"[INFO] Using '{main_table}' as main symbols table with {max_count} records")
            
            # Get column names from the main table
            sqlite_cursor.execute(f"PRAGMA table_info({main_table});")
            columns_info = sqlite_cursor.fetchall()
            column_names = [col[1] for col in columns_info]
            print(f"[INFO] Available columns: {column_names}")
            
            # Try to map common column names
            symbol_col = None
            name_col = None
            security_id_col = None
            exchange_col = None
            segment_col = None
            
            # Common column name mappings
            for col in column_names:
                col_lower = col.lower()
                if col_lower in ['symbol', 'symbol_name', 'tradingsymbol', 'trading_symbol']:
                    symbol_col = col
                elif col_lower in ['name', 'display_name', 'company_name', 'instrument_name']:
                    name_col = col
                elif col_lower in ['security_id', 'instrument_token', 'token', 'securityid']:
                    security_id_col = col
                elif col_lower in ['exchange', 'exch_id', 'exch']:
                    exchange_col = col
                elif col_lower in ['segment', 'seg']:
                    segment_col = col
            
            print(f"[INFO] Mapped columns:")
            print(f"  Symbol: {symbol_col}")
            print(f"  Name: {name_col}")
            print(f"  Security ID: {security_id_col}")
            print(f"  Exchange: {exchange_col}")
            print(f"  Segment: {segment_col}")
            
            # Build the SELECT query
            select_cols = []
            if symbol_col:
                select_cols.append(symbol_col)
            if name_col:
                select_cols.append(name_col)
            if security_id_col:
                select_cols.append(security_id_col)
            if exchange_col:
                select_cols.append(exchange_col)
            if segment_col:
                select_cols.append(segment_col)
            
            if not select_cols:
                print("[ERROR] Could not map any required columns")
                return False
            
            # Fetch all data from SQLite
            query = f"SELECT {', '.join(select_cols)} FROM {main_table}"
            
            # Add WHERE clause to filter NSE equity if possible
            if exchange_col and segment_col:
                query += f" WHERE {exchange_col} = 'NSE' AND {segment_col} = 'E'"
            elif exchange_col:
                query += f" WHERE {exchange_col} = 'NSE'"
            
            print(f"[INFO] Executing query: {query}")
            sqlite_cursor.execute(query)
            
            # Insert data into PostgreSQL
            inserted_count = 0
            batch_size = 1000
            batch_data = []
            
            while True:
                rows = sqlite_cursor.fetchmany(batch_size)
                if not rows:
                    break
                
                for row in rows:
                    try:
                        # Map the row data
                        symbol = row[0] if symbol_col and len(row) > 0 else None
                        name = row[1] if name_col and len(row) > 1 else symbol
                        sec_id = row[2] if security_id_col and len(row) > 2 else None
                        exchange = row[3] if exchange_col and len(row) > 3 else 'NSE'
                        segment = row[4] if segment_col and len(row) > 4 else 'E'
                        
                        # Skip if essential data is missing
                        if not symbol or not sec_id:
                            continue
                        
                        # Clean up the data
                        symbol = str(symbol).strip().upper()
                        name = str(name).strip() if name else symbol
                        
                        try:
                            sec_id = int(sec_id)
                        except (ValueError, TypeError):
                            continue
                        
                        exchange = str(exchange).strip().upper()
                        segment = str(segment).strip().upper()
                        
                        # Map segment variations
                        if segment in ['EQ', 'EQUITY', 'E']:
                            segment = 'E'
                        
                        # Insert into PostgreSQL
                        pg_conn.execute(text("""
                            INSERT INTO instruments (symbol_name, display_name, security_id, exch_id, segment)
                            VALUES (:symbol, :name, :sec_id, :exchange, :segment)
                            ON CONFLICT DO NOTHING
                        """), {
                            'symbol': symbol,
                            'name': name,
                            'sec_id': sec_id,
                            'exchange': exchange,
                            'segment': segment
                        })
                        
                        inserted_count += 1
                        
                        if inserted_count % 1000 == 0:
                            print(f"[INFO] Inserted {inserted_count} records...")
                    
                    except Exception as e:
                        print(f"[WARNING] Error inserting row {row}: {e}")
                        continue
            
            print(f"[SUCCESS] Migration completed! Inserted {inserted_count} symbols into PostgreSQL")
            
            # Verify the migration
            result = pg_conn.execute(text("SELECT COUNT(*) FROM instruments")).fetchone()
            print(f"[INFO] Total records in PostgreSQL instruments table: {result[0]}")
            
            # Show sample data
            sample_rows = pg_conn.execute(text("""
                SELECT symbol_name, display_name, security_id, exch_id, segment 
                FROM instruments 
                WHERE exch_id = 'NSE' AND segment = 'E'
                LIMIT 10
            """)).fetchall()
            
            print("[INFO] Sample migrated data:")
            for row in sample_rows:
                print(f"  {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]}")
        
        sqlite_conn.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        return False

if __name__ == "__main__":
    print("Starting migration from all_symbol.db to PostgreSQL...")
    
    if not os.path.exists('all_symbol.db'):
        print("[ERROR] all_symbol.db not found in current directory")
        sys.exit(1)
    
    success = migrate_symbols_to_postgres()
    if success:
        print("[SUCCESS] Symbol migration completed successfully!")
    else:
        print("[ERROR] Symbol migration failed!")
        sys.exit(1)