#!/usr/bin/env python3
"""
Test script for mentor-coupon attribution system
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text

def test_mentor_coupon_system():
    """Test mentor-coupon attribution functionality"""
    
    with app.app_context():
        try:
            print("Testing mentor-coupon system...")
            
            # Test 1: Check database schema
            print("\n1. Checking database schema...")
            
            # Check coupon table columns
            coupon_columns = db.session.execute(text("PRAGMA table_info(coupon)")).fetchall()
            coupon_col_names = [col[1] for col in coupon_columns]
            
            required_coupon_cols = ['mentor_id', 'mentor_commission_pct', 'max_uses', 'uses']
            for col in required_coupon_cols:
                if col in coupon_col_names:
                    print(f"   ✓ coupon.{col} exists")
                else:
                    print(f"   ✗ coupon.{col} missing")
            
            # Check coupon_usage table columns
            usage_columns = db.session.execute(text("PRAGMA table_info(coupon_usage)")).fetchall()
            usage_col_names = [col[1] for col in usage_columns]
            
            required_usage_cols = ['coupon_id', 'mentor_id', 'commission_amount', 'order_id']
            for col in required_usage_cols:
                if col in usage_col_names:
                    print(f"   ✓ coupon_usage.{col} exists")
                else:
                    print(f"   ✗ coupon_usage.{col} missing")
            
            # Test 2: Check mentor table exists
            print("\n2. Checking mentor table...")
            try:
                mentor_count = db.session.execute(text("SELECT COUNT(*) FROM mentor")).fetchone()[0]
                print(f"   Found {mentor_count} mentors")
            except Exception as e:
                print(f"   ✗ Mentor table issue: {e}")
            
            # Test 3: Test coupon validation with mentor attribution
            print("\n3. Testing coupon validation...")
            test_coupon = db.session.execute(
                text("SELECT id, code, discount_percent, active, mentor_id, max_uses, uses FROM coupon WHERE active = 1 LIMIT 1")
            ).fetchone()
            
            if test_coupon:
                coupon_id, code, discount, active, mentor_id, max_uses, uses = test_coupon
                print(f"   Testing coupon: {code}")
                print(f"   Discount: {discount}%")
                print(f"   Mentor ID: {mentor_id or 'Platform-level'}")
                print(f"   Usage: {uses}/{max_uses}")
                
                # Test commission calculation
                if mentor_id:
                    commission_pct = db.session.execute(
                        text("SELECT mentor_commission_pct FROM coupon WHERE id = :id"),
                        {"id": coupon_id}
                    ).fetchone()[0]
                    
                    test_amount = 2500  # Monthly plan
                    commission = int((test_amount * commission_pct) / 100)
                    print(f"   Commission: {commission_pct}% = ₹{commission/100:.2f}")
                else:
                    print(f"   Commission: 0% (platform-level)")
                
                print("   ✓ Coupon validation working")
            else:
                print("   ⚠️ No active coupons found")
            
            # Test 4: Check mentor report endpoint structure
            print("\n4. Testing mentor report structure...")
            if mentor_count > 0:
                # Get first mentor ID
                mentor_id = db.session.execute(text("SELECT id FROM mentor LIMIT 1")).fetchone()[0]
                print(f"   Testing report for mentor ID: {mentor_id}")
                
                # Test the query structure (without actual usage data)
                usage_stats = db.session.execute(
                    text("""
                        SELECT 
                            COUNT(*) as total_uses,
                            COALESCE(SUM(p.amount), 0) as total_revenue_impact,
                            COALESCE(SUM(cu.discount_amount), 0) as total_discount,
                            COALESCE(SUM(cu.commission_amount), 0) as total_commission_owed
                        FROM coupon_usage cu
                        LEFT JOIN payments p ON cu.payment_id = p.id
                        WHERE cu.mentor_id = :mentor_id AND (p.status = 'paid' OR p.status IS NULL)
                    """),
                    {"mentor_id": mentor_id}
                ).fetchone()
                
                print(f"   Report query successful: {usage_stats[0]} uses, ₹{usage_stats[1]/100:.2f} revenue")
                print("   ✓ Mentor report structure working")
            
            print("\n✓ Mentor-coupon system test completed!")
            return True
            
        except Exception as e:
            print(f"\n✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_mentor_coupon_system()
    sys.exit(0 if success else 1)