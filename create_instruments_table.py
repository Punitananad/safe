#!/usr/bin/env python3
"""
Create instruments table with basic NSE equity symbols
"""

import os
import sys
from sqlalchemy import create_engine, text
from database_config import get_postgres_url

def create_instruments_table():
    """Create instruments table with basic NSE equity symbols"""
    try:
        # Connect to PostgreSQL
        engine = create_engine(get_postgres_url())
        
        with engine.connect() as conn:
            # Create instruments table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS instruments (
                    id SERIAL PRIMARY KEY,
                    symbol_name VARCHAR(50) NOT NULL,
                    display_name VARCHAR(200),
                    security_id INTEGER NOT NULL,
                    exch_id VARCHAR(10) NOT NULL DEFAULT 'NSE',
                    segment VARCHAR(10) NOT NULL DEFAULT 'E',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Create indexes for better performance
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_instruments_symbol 
                ON instruments(symbol_name, exch_id, segment)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_instruments_display 
                ON instruments(display_name)
            """))
            
            # Insert basic NSE equity symbols
            basic_symbols = [
                ('SBIN', 'State Bank of India', 1333),
                ('HDFCBANK', 'HDFC Bank Limited', 1330),
                ('TCS', 'Tata Consultancy Services Limited', 11536),
                ('RELIANCE', 'Reliance Industries Limited', 2885),
                ('INFY', 'Infosys Limited', 1594),
                ('ICICIBANK', 'ICICI Bank Limited', 4963),
                ('HINDUNILVR', 'Hindustan Unilever Limited', 1394),
                ('ITC', 'ITC Limited', 1660),
                ('KOTAKBANK', 'Kotak Mahindra Bank Limited', 1922),
                ('LT', 'Larsen & Toubro Limited', 11483),
                ('BAJFINANCE', 'Bajaj Finance Limited', 81),
                ('BHARTIARTL', 'Bharti Airtel Limited', 10604),
                ('ASIANPAINT', 'Asian Paints Limited', 42),
                ('MARUTI', 'Maruti Suzuki India Limited', 10999),
                ('AXISBANK', 'Axis Bank Limited', 5900),
                ('WIPRO', 'Wipro Limited', 3787),
                ('ULTRACEMCO', 'UltraTech Cement Limited', 11532),
                ('NESTLEIND', 'Nestle India Limited', 17963),
                ('TITAN', 'Titan Company Limited', 3506),
                ('POWERGRID', 'Power Grid Corporation of India Limited', 14977)
            ]
            
            # Check if data already exists
            result = conn.execute(text("SELECT COUNT(*) FROM instruments")).fetchone()
            if result[0] == 0:
                # Insert basic symbols
                for symbol, name, sec_id in basic_symbols:
                    conn.execute(text("""
                        INSERT INTO instruments (symbol_name, display_name, security_id, exch_id, segment)
                        VALUES (:symbol, :name, :sec_id, 'NSE', 'E')
                    """), {'symbol': symbol, 'name': name, 'sec_id': sec_id})
                
                print(f"[SUCCESS] Inserted {len(basic_symbols)} basic NSE equity symbols")
            else:
                print(f"[INFO] Instruments table already contains {result[0]} symbols")
            
            # conn.commit()  # Not needed with autocommit
            print("[SUCCESS] Instruments table created successfully")
            
    except Exception as e:
        print(f"[ERROR] Error creating instruments table: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Creating instruments table...")
    success = create_instruments_table()
    if success:
        print("[SUCCESS] Instruments table setup complete!")
    else:
        print("[ERROR] Failed to create instruments table")
        sys.exit(1)