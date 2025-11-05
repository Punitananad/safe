#!/usr/bin/env python3
"""
Create tables in PostgreSQL
"""
import os
os.environ['DATABASE_TYPE'] = 'postgres'

from app import app, db

def create_tables():
    """Create all tables in PostgreSQL"""
    with app.app_context():
        try:
            print("Creating tables in PostgreSQL...")
            db.create_all()
            print("✓ All tables created successfully")
        except Exception as e:
            print(f"✗ Error creating tables: {e}")

if __name__ == "__main__":
    create_tables()