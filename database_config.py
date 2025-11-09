import os
from urllib.parse import quote_plus

def get_postgres_url():
    """Get PostgreSQL URL with proper configuration"""
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', 'Punit@1465')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'calculatentrade_db')
    
    encoded_password = quote_plus(db_password)
    
    # Use postgresql:// instead of postgresql+psycopg2:// for better compatibility
    return f"postgresql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"

def get_database_engine_options():
    """Get database engine options for PostgreSQL"""
    return {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "connect_args": {
            "options": "-c timezone=UTC",
            "client_encoding": "utf8"
        }
    }