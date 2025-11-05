#!/usr/bin/env python3
"""
Migration script to move data from SQLite to PostgreSQL
"""
import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from database_config import get_postgres_url
from urllib.parse import urlparse

def get_postgres_connection():
    """Get PostgreSQL connection"""
    url = get_postgres_url()
    parsed = urlparse(url)
    
    return psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        database=parsed.path[1:],  # Remove leading slash
        user=parsed.username,
        password=parsed.password
    )

def get_sqlite_connection():
    """Get SQLite connection"""
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'calculatentrade.db')
    return sqlite3.connect(db_path)

def migrate_table(table_name, sqlite_conn, postgres_conn):
    """Migrate a single table from SQLite to PostgreSQL"""
    print(f"Migrating table: {table_name}")
    
    # Get SQLite data
    sqlite_cursor = sqlite_conn.cursor()
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()
    
    if not rows:
        print(f"  No data in {table_name}")
        return
    
    # Get column names
    column_names = [description[0] for description in sqlite_cursor.description]
    
    # Prepare PostgreSQL insert
    postgres_cursor = postgres_conn.cursor()
    
    # Create placeholders for INSERT
    placeholders = ', '.join(['%s'] * len(column_names))
    columns_str = ', '.join(column_names)
    
    insert_query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
    
    # Insert data
    try:
        postgres_cursor.executemany(insert_query, rows)
        postgres_conn.commit()
        print(f"  Migrated {len(rows)} rows")
    except Exception as e:
        print(f"  Error migrating {table_name}: {e}")
        postgres_conn.rollback()

def main():
    """Main migration function"""
    print("Starting migration from SQLite to PostgreSQL...")
    
    # Check if SQLite database exists
    sqlite_path = os.path.join(os.path.dirname(__file__), 'instance', 'calculatentrade.db')
    if not os.path.exists(sqlite_path):
        print(f"SQLite database not found at: {sqlite_path}")
        return
    
    try:
        # Connect to databases
        sqlite_conn = get_sqlite_connection()
        postgres_conn = get_postgres_connection()
        
        print("Connected to both databases")
        
        # Tables to migrate (in order to handle foreign keys)
        tables = [
            'users',
            'user_settings',
            'email_verify_otp',
            'reset_otp',
            'intraday_trades',
            'delivery_trades',
            'swing_trades',
            'mtf_trades',
            'fo_trades',
            'trade_splits',
            'preview_templates',
            'ai_plan_templates'
        ]
        
        # Clear existing data in PostgreSQL (optional)
        postgres_cursor = postgres_conn.cursor()
        for table in reversed(tables):  # Reverse order for foreign keys
            try:
                postgres_cursor.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
                print(f"Cleared table: {table}")
            except Exception as e:
                print(f"Could not clear {table}: {e}")
        postgres_conn.commit()
        
        # Migrate each table
        for table in tables:
            try:
                migrate_table(table, sqlite_conn, postgres_conn)
            except Exception as e:
                print(f"Error with table {table}: {e}")
        
        print("Migration completed!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        if 'sqlite_conn' in locals():
            sqlite_conn.close()
        if 'postgres_conn' in locals():
            postgres_conn.close()

if __name__ == "__main__":
    main()