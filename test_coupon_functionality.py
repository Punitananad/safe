#!/usr/bin/env python3
"""
Test script for coupon functionality.
This script tests the coupon validation and application logic.
"""

import os
import sys
import requests
import json

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_coupon_api():
    """Test the coupon API endpoints"""
    
    base_url = "http://localhost:5000"
    
    # Test data
    test_coupon = "TEST10"  # Assuming this exists in admin panel
    
    print("🧪 Testing Coupon Functionality")
    print("=" * 50)
    
    # Test 1: Apply valid coupon
    print("\n1. Testing valid coupon application...")
    try:
        response = requests.post(f"{base_url}/api/apply-coupon", 
                               json={
                                   "coupon_code": test_coupon,
                                   "plan_type": "monthly"
                               },
                               headers={"Content-Type": "application/json"})
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"✅ Valid coupon applied successfully")
                print(f"   Discount: {data.get('discount_percent')}%")
                print(f"   Original: ₹{data.get('original_amount', 0)/100}")
                print(f"   Final: ₹{data.get('final_amount', 0)/100}")
                print(f"   Savings: ₹{data.get('discount_amount', 0)/100}")
            else:
                print(f"❌ Coupon validation failed: {data.get('error')}")
        else:
            print(f"❌ API request failed: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the app is running on localhost:5000")
        return
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    # Test 2: Apply invalid coupon
    print("\n2. Testing invalid coupon...")
    try:
        response = requests.post(f"{base_url}/api/apply-coupon", 
                               json={
                                   "coupon_code": "INVALID123",
                                   "plan_type": "monthly"
                               },
                               headers={"Content-Type": "application/json"})
        
        if response.status_code == 400:
            data = response.json()
            if not data.get("success"):
                print(f"✅ Invalid coupon correctly rejected: {data.get('error')}")
            else:
                print("❌ Invalid coupon was accepted (this shouldn't happen)")
        else:
            print(f"❌ Unexpected response code: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    # Test 3: Test with yearly plan
    print("\n3. Testing yearly plan with coupon...")
    try:
        response = requests.post(f"{base_url}/api/apply-coupon", 
                               json={
                                   "coupon_code": test_coupon,
                                   "plan_type": "yearly"
                               },
                               headers={"Content-Type": "application/json"})
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"✅ Yearly plan coupon applied successfully")
                print(f"   Original: ₹{data.get('original_amount', 0)/100}")
                print(f"   Final: ₹{data.get('final_amount', 0)/100}")
            else:
                print(f"❌ Yearly coupon failed: {data.get('error')}")
        else:
            print(f"❌ API request failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    print("\n" + "=" * 50)
    print("🏁 Coupon functionality testing completed!")
    print("\nTo create test coupons:")
    print("1. Go to http://localhost:5000/admin")
    print("2. Login with admin credentials")
    print("3. Create coupons in the admin panel")

if __name__ == "__main__":
    test_coupon_api()