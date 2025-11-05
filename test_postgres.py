#!/usr/bin/env python3
"""
Test PostgreSQL connection and basic operations
"""
import os
from database_config import get_postgres_url
from app import app, db, User

def test_connection():
    """Test PostgreSQL connection"""
    print("Testing PostgreSQL connection...")
    
    # Set environment to use PostgreSQL
    os.environ['DATABASE_TYPE'] = 'postgres'
    
    with app.app_context():
        try:
            # Test connection
            db.engine.execute('SELECT 1')
            print("✓ PostgreSQL connection successful")
            
            # Create tables
            db.create_all()
            print("✓ Tables created successfully")
            
            # Test user creation
            test_user = User(
                email='test@example.com',
                verified=True
            )
            test_user.set_password('testpassword')
            
            db.session.add(test_user)
            db.session.commit()
            print("✓ Test user created")
            
            # Test user query
            user = User.query.filter_by(email='test@example.com').first()
            if user:
                print("✓ User query successful")
            
            # Clean up
            db.session.delete(user)
            db.session.commit()
            print("✓ Test user deleted")
            
            print("\nPostgreSQL setup is working correctly!")
            
        except Exception as e:
            print(f"✗ Error: {e}")
            return False
    
    return True

if __name__ == "__main__":
    test_connection()