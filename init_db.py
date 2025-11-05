#!/usr/bin/env python3
"""
Database initialization script for CalculatenTrade
Handles database creation with proper Flask application context
"""

import os
import sys
from app import app, init_app_database

def init_database():
    """Initialize database with proper application context"""
    try:
        init_app_database()
        print("🎉 Database initialization completed successfully!")
        return True
            
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)