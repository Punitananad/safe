import os
import logging
from urllib.parse import quote_plus

# Configure database logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)

def get_postgres_url():
    """Get PostgreSQL connection URL with production optimizations"""
    # Check for full DATABASE_URL first (for production)
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        # Handle Heroku postgres:// URLs
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        # Add production connection parameters if not present
        if os.getenv('FLASK_ENV') == 'production' and '?' not in database_url:
            database_url += '?sslmode=require&connect_timeout=10'
        
        return database_url
    
    # Fallback to individual components
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', 'Punit@1465')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'calculatentrade_db')
    
    encoded_password = quote_plus(db_password)
    
    # Add SSL for production
    ssl_param = 'sslmode=require' if os.getenv('FLASK_ENV') == 'production' else 'sslmode=prefer'
    
    return f"postgresql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?{ssl_param}&connect_timeout=10"

def get_database_engine_options():
    """Get database engine options based on environment"""
    if os.getenv('FLASK_ENV') == 'production':
        # Production optimizations
        try:
            from production_db_config import get_production_database_config
            _, engine_options = get_production_database_config()
            return engine_options
        except Exception as e:
            print(f"Warning: Could not load production DB config: {e}")
            # Fallback production settings
            return {
                'pool_pre_ping': True,
                'pool_recycle': 3600,
                'pool_timeout': 30,
                'pool_size': 10,
                'max_overflow': 20,
                'echo': False,
                'connect_args': {
                    'connect_timeout': 10,
                    'application_name': 'calculatentrade_prod',
                    'options': '-c timezone=UTC',
                    'client_encoding': 'utf8'
                }
            }
    else:
        return {
            'pool_pre_ping': True,
            'pool_size': 5,
            'max_overflow': 10,
            'pool_recycle': 300,
            'echo': False,
            'connect_args': {
                'options': '-c timezone=UTC',
                'client_encoding': 'utf8'
            }
        }