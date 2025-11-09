#!/usr/bin/env python3
"""
Test script to check if the dashboard route works without errors
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Create a minimal Flask app for testing
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'test-secret-key'

db = SQLAlchemy(app)

# Import the models and routes after setting up the app
try:
    from journal import calculatentrade_bp, Trade, Strategy, Rule, Mistake, Challenge
    app.register_blueprint(calculatentrade_bp)
    
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Test the dashboard route
        with app.test_client() as client:
            # Mock a session to bypass subscription check
            with client.session_transaction() as sess:
                sess['email'] = 'test@example.com'
                sess['user_id'] = 1
            
            print("Testing dashboard route...")
            response = client.get('/calculatentrade_journal/dashboard')
            
            if response.status_code == 200:
                print("✅ Dashboard route works successfully!")
                print(f"Response length: {len(response.data)} bytes")
            else:
                print(f"❌ Dashboard route failed with status code: {response.status_code}")
                print(f"Response: {response.data.decode()[:500]}...")
                
except Exception as e:
    print(f"❌ Error testing dashboard: {e}")
    import traceback
    print(f"Traceback: {traceback.format_exc()}")