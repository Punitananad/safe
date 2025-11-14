#!/usr/bin/env python3
"""
Simple script to run the Flask app with external access
Run this with: python run_app.py
"""

if __name__ == "__main__":
    # Initialize database first
    try:
        from init_db import init_database
        init_database()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")
    
    # Import and run the Flask app
    from app import app
    
    print("Starting Flask app...")
    print("Your PC's IP address is: 192.168.1.75")
    print("Access the app from your phone at: http://192.168.1.75:5000")
    print("Press Ctrl+C to stop the server")
    
    # Run the app with external access
    app.run(host='0.0.0.0', port=5000, debug=True)