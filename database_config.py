import os
from urllib.parse import quote_plus

def get_database_url():
    """Get database URL based on environment"""
    
    # Check database type from env
    db_type = os.getenv('DATABASE_TYPE', 'sqlite')
    
    if db_type == 'postgres':
        # PostgreSQL
        db_user = os.getenv('DB_USER', 'cnt_user')
        db_password = os.getenv('DB_PASSWORD', 'CNT_SecurePass_2024!')
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'calculatentrade_db')
        
        encoded_password = quote_plus(db_password)
        return f"postgresql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"
    else:
        # SQLite (default)
        db_location = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'calculatentrade.db')
        return f"sqlite:///{db_location}"

def get_postgres_url():
    """Get PostgreSQL URL for local testing"""
    db_user = os.getenv('DB_USER', 'cnt_user')
    db_password = os.getenv('DB_PASSWORD', 'CNT_SecurePass_2024!')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'calculatentrade_db')
    
    encoded_password = quote_plus(db_password)
    return f"postgresql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"