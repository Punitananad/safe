#!/usr/bin/env python3
"""
Script to add sample data for testing the mentor payment system
"""

import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

def add_sample_data():
    """Add sample data for testing"""
    
    # Database path
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'database.db')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Add sample mentor
        cursor.execute("""
            INSERT OR IGNORE INTO mentor 
            (mentor_id, password_hash, name, email, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            'MNT950447',
            generate_password_hash('password123'),
            'Punit Anand',
            'punitanand571@gmail.com',
            1,
            datetime.now()
        ))
        
        mentor_id = cursor.lastrowid or 1
        
        # Add sample coupon
        cursor.execute("""
            INSERT OR IGNORE INTO coupon 
            (code, discount_percent, created_by, active, mentor_id, max_uses, uses, mentor_commission_pct, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'PUNIT10',
            10,
            'admin',
            1,
            mentor_id,
            100,
            5,
            10.0,
            datetime.now()
        ))
        
        # Add sample users
        sample_users = [
            ('user1@example.com', 'John Doe', 1),
            ('user2@example.com', 'Jane Smith', 1),
            ('user3@example.com', 'Bob Johnson', 1),
            ('user4@example.com', 'Alice Brown', 1),
            ('user5@example.com', 'Charlie Wilson', 1)
        ]
        
        for email, name, verified in sample_users:
            cursor.execute("""
                INSERT OR IGNORE INTO users 
                (email, name, verified, subscription_active, registered_on)
                VALUES (?, ?, ?, ?, ?)
            """, (email, name, verified, 1, datetime.now()))
        
        # Add sample coupon usage
        cursor.execute("SELECT id FROM users LIMIT 5")
        user_ids = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT id FROM coupon WHERE code = 'PUNIT10'")
        coupon_id = cursor.fetchone()[0]
        
        for i, user_id in enumerate(user_ids):
            cursor.execute("""
                INSERT OR IGNORE INTO coupon_usage 
                (user_id, coupon_id, coupon_code, mentor_id, discount_amount, commission_amount, used_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                coupon_id,
                'PUNIT10',
                mentor_id,
                25000,  # ₹250 discount
                25000,  # ₹250 commission
                datetime.now() - timedelta(days=i*5)
            ))
        
        # Add sample payment history
        sample_payments = [
            (mentor_id, 10000, 'UPI', '123456789012', 'January 2025', 2, 'Payment for January 2025. Monthly commission settlement', 'admin'),
            (mentor_id, 15000, 'Bank Transfer', 'HDFC12345678901', 'February 2025', 3, 'Payment for February 2025. Includes bonus', 'admin')
        ]
        
        for payment_data in sample_payments:
            cursor.execute("""
                INSERT OR IGNORE INTO mentor_payments 
                (mentor_id, amount, payment_date, payment_method, reference_number, 
                 period_start, commission_count, notes, paid_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                payment_data[0],  # mentor_id
                payment_data[1],  # amount
                datetime.now() - timedelta(days=30),  # payment_date
                payment_data[2],  # payment_method
                payment_data[3],  # reference_number
                payment_data[4],  # period_start
                payment_data[5],  # commission_count
                payment_data[6],  # notes
                payment_data[7],  # paid_by
                datetime.now()    # created_at
            ))
        
        conn.commit()
        print("Sample data added successfully!")
        
        # Show summary
        cursor.execute("SELECT COUNT(*) FROM mentor")
        mentor_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM coupon")
        coupon_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM coupon_usage")
        usage_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM mentor_payments")
        payment_count = cursor.fetchone()[0]
        
        print(f"\nData Summary:")
        print(f"  Mentors: {mentor_count}")
        print(f"  Coupons: {coupon_count}")
        print(f"  Users: {user_count}")
        print(f"  Coupon Usage: {usage_count}")
        print(f"  Payments: {payment_count}")
        
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Adding sample data...")
    success = add_sample_data()
    if success:
        print("Sample data added successfully!")
    else:
        print("Failed to add sample data!")