#!/usr/bin/env python3
"""
Test the journal dashboard fixes on Windows
"""

import os
import sys
import traceback
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test if all imports work correctly"""
    print("Testing imports...")
    try:
        from flask import Flask, render_template
        from flask_sqlalchemy import SQLAlchemy
        print("[OK] Flask imports successful")
        
        # Test journal imports
        from journal import calculatentrade_bp, safe_log_error, _get_empty_dashboard_data
        print("[OK] Journal imports successful")
        
        return True
    except Exception as e:
        print(f"[ERROR] Import error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return False

def test_safe_logging():
    """Test the safe logging function"""
    print("\nTesting safe logging...")
    try:
        from journal import safe_log_error
        safe_log_error("Test error message")
        print("[OK] Safe logging works")
        return True
    except Exception as e:
        print(f"[ERROR] Safe logging error: {e}")
        return False

def test_empty_dashboard_data():
    """Test the empty dashboard data function"""
    print("\nTesting empty dashboard data...")
    try:
        from journal import _get_empty_dashboard_data
        data = _get_empty_dashboard_data()
        required_keys = ['recent_trades', 'win_rate', 'total_trades', 'total_pnl']
        
        for key in required_keys:
            if key not in data:
                print(f"[ERROR] Missing key: {key}")
                return False
        
        print("[OK] Empty dashboard data structure is correct")
        return True
    except Exception as e:
        print(f"[ERROR] Empty dashboard data error: {e}")
        return False

def test_minimal_app():
    """Test creating a minimal Flask app with the journal blueprint"""
    print("\nTesting minimal Flask app...")
    try:
        from flask import Flask
        from flask_sqlalchemy import SQLAlchemy
        from journal import calculatentrade_bp
        
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SECRET_KEY'] = 'test-key'
        
        db = SQLAlchemy(app)
        app.register_blueprint(calculatentrade_bp)
        
        print("[OK] Minimal Flask app created successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Minimal app error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return False

def main():
    """Run all tests"""
    print("Testing Journal Dashboard Fixes")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_safe_logging,
        test_empty_dashboard_data,
        test_minimal_app
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"[ERROR] Test {test.__name__} failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("All tests passed! The journal dashboard fixes should work.")
    else:
        print("Some tests failed. Please check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)