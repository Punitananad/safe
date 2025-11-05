#!/usr/bin/env python3
"""
Test script to check mentor table structure and create a test mentor
"""
import sqlite3
import os
from werkzeug.security import generate_password_hash

def test_mentor_table():
    # Path to the database
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'calculatentrade.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check mentor table structure
        print("=== MENTOR TABLE STRUCTURE ===")
        cursor.execute("PRAGMA table_info(mentor)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"Column: {col[1]}, Type: {col[2]}, Default: {col[4]}")
        
        # Check if there are any existing mentors
        print("\n=== EXISTING MENTORS ===")
        cursor.execute("SELECT mentor_id, name, email, commission_pct FROM mentor")
        mentors = cursor.fetchall()
        for mentor in mentors:
            print(f"ID: {mentor[0]}, Name: {mentor[1]}, Email: {mentor[2]}, Commission: {mentor[3]}%")
        
        if not mentors:
            print("No mentors found")
        
        # Try to create a test mentor directly in SQL
        print("\n=== CREATING TEST MENTOR ===")
        test_mentor_id = "MNT999999"
        test_password_hash = generate_password_hash("testpass123")
        
        try:
            cursor.execute("""
                INSERT INTO mentor (mentor_id, password_hash, name, email, commission_pct, created_by_admin_id, active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (test_mentor_id, test_password_hash, "Test Mentor", "test@example.com", 40.0, 1, 1))
            
            conn.commit()
            print(f"Successfully created test mentor: {test_mentor_id}")
            
            # Verify the mentor was created
            cursor.execute("SELECT * FROM mentor WHERE mentor_id = ?", (test_mentor_id,))
            result = cursor.fetchone()
            if result:
                print(f"Verified: Mentor created with commission_pct = {result[5]}")
            
            # Clean up - delete the test mentor
            cursor.execute("DELETE FROM mentor WHERE mentor_id = ?", (test_mentor_id,))
            conn.commit()
            print("Test mentor cleaned up")
            
        except Exception as e:
            print(f"Error creating test mentor: {e}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    test_mentor_table()