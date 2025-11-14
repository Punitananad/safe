#!/usr/bin/env python3
"""
Run admin authentication tests
"""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

def main():
    print("🚀 Admin Authentication Test Suite")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("app.py").exists():
        print("❌ app.py not found. Please run this from the project directory.")
        sys.exit(1)
    
    print("📋 Available Tests:")
    print("1. Run automated test script")
    print("2. Open manual test page in browser")
    print("3. Start Flask app for testing")
    print("4. Run all tests")
    
    choice = input("\nEnter your choice (1-4): ").strip()
    
    if choice == "1":
        print("\n🔧 Running automated tests...")
        try:
            subprocess.run([sys.executable, "test_admin_auth.py"], check=True)
        except subprocess.CalledProcessError:
            print("❌ Automated tests failed")
        except FileNotFoundError:
            print("❌ test_admin_auth.py not found")
    
    elif choice == "2":
        print("\n🌐 Opening manual test page...")
        print("Make sure Flask app is running first!")
        webbrowser.open("http://localhost:5000/admin/test")
        
    elif choice == "3":
        print("\n🏃 Starting Flask app...")
        print("Press Ctrl+C to stop")
        try:
            subprocess.run([sys.executable, "app.py"], check=True)
        except KeyboardInterrupt:
            print("\n⏹️ Flask app stopped")
        except subprocess.CalledProcessError:
            print("❌ Flask app failed to start")
    
    elif choice == "4":
        print("\n🔄 Running all tests...")
        
        # Start Flask app in background
        print("1. Starting Flask app...")
        flask_process = subprocess.Popen([sys.executable, "app.py"])
        
        # Wait for app to start
        print("2. Waiting for app to start...")
        time.sleep(3)
        
        try:
            # Run automated tests
            print("3. Running automated tests...")
            subprocess.run([sys.executable, "test_admin_auth.py"], check=True)
            
            # Open manual test page
            print("4. Opening manual test page...")
            webbrowser.open("http://localhost:5000/admin/test")
            
            print("\n✅ All tests completed!")
            print("Check the browser for manual testing")
            
        except Exception as e:
            print(f"❌ Error during tests: {e}")
        finally:
            # Stop Flask app
            print("5. Stopping Flask app...")
            flask_process.terminate()
            flask_process.wait()
    
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()