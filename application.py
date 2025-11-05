#!/usr/bin/env python3
"""
AWS Elastic Beanstalk entry point
"""
import os
import sys

# Set up environment for AWS deployment
os.environ['SMARTAPI_DISABLE_NETWORK'] = '1'
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Import the Flask application
from run_app import setup_environment
from app import app, db

# Initialize environment
setup_environment()

# Initialize database on first run
with app.app_context():
    try:
        db.create_all()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization warning: {e}")

# Re-enable network calls for runtime
os.environ.pop('SMARTAPI_DISABLE_NETWORK', None)

# This is what Elastic Beanstalk will use
application = app

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=5000)