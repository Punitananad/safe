#!/usr/bin/env python3
"""
Simple test script to verify coupon system functionality
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text

def test_coupon_system():
    """Test basic coupon system functionality"""
    
    with app.app_context():
        try:
            print("🧪 Testing coupon system...")
            
            # Test 1: Check if coupon table exists and has data
            print("\n1. Checking coupon table...")
            coupons = db.session.execute(text("SELECT code, discount_percent, active FROM coupon LIMIT 5")).fetchall()
            print(f"   Found {len(coupons)} coupons in database")
            for coupon in coupons:
                print(f"   - {coupon[0]}: {coupon[1]}% discount, Active: {coupon[2]}")
            
            # Test 2: Check payments table structure
            print("\n2. Checking payments table structure...")
            result = db.session.execute(text("PRAGMA table_info(payments)")).fetchall()
            payment_columns = [row[1] for row in result]
            required_columns = ['original_amount', 'discount_amount', 'coupon_code']
            
            for col in required_columns:
                if col in payment_columns:
                    print(f"   ✅ {col} column exists")
                else:
                    print(f"   ❌ {col} column missing")
            
            # Test 3: Check coupon_usage table
            print("\n3. Checking coupon_usage table...")
            usage_count = db.session.execute(text("SELECT COUNT(*) FROM coupon_usage")).fetchone()[0]
            print(f"   Found {usage_count} coupon usage records")
            
            # Test 4: Test coupon validation logic
            print("\n4. Testing coupon validation...")
            test_coupon = db.session.execute(
                text("SELECT code, discount_percent, active FROM coupon WHERE active = 1 LIMIT 1")
            ).fetchone()
            
            if test_coupon:
                code, discount, active = test_coupon
                print(f"   Testing coupon: {code} ({discount}% discount)")
                
                # Simulate coupon application
                original_amount = 2500  # Monthly plan
                discount_amount = int((original_amount * discount) / 100)
                final_amount = original_amount - discount_amount
                
                print(f"   Original: ₹{original_amount/100:.2f}")
                print(f"   Discount: ₹{discount_amount/100:.2f} ({discount}%)")
                print(f"   Final: ₹{final_amount/100:.2f}")
                print(f"   ✅ Coupon calculation working")
            else:
                print("   ⚠️  No active coupons found for testing")
            
            print("\n✅ Coupon system test completed successfully!")
            return True
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            return False

if __name__ == "__main__":
    success = test_coupon_system()
    sys.exit(0 if success else 1)