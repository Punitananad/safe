# Production database configuration with connection pooling and optimizations
import os
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

def get_production_database_config():
    """Get production database configuration with connection pooling"""
    
    # Database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required for production")
    
    # Connection pool settings for production
    engine_options = {
        'poolclass': QueuePool,
        'pool_size': 20,  # Number of connections to maintain in pool
        'max_overflow': 30,  # Additional connections beyond pool_size
        'pool_pre_ping': True,  # Validate connections before use
        'pool_recycle': 3600,  # Recycle connections every hour
        'pool_timeout': 30,  # Timeout for getting connection from pool
        'connect_args': {
            'connect_timeout': 10,
            'application_name': 'calculatentrade_prod',
            'options': '-c default_transaction_isolation=read_committed'
        }
    }
    
    return database_url, engine_options

def get_database_health_check():
    """Database health check for monitoring"""
    try:
        from sqlalchemy import text
        from app import db
        
        # Simple query to check database connectivity
        result = db.session.execute(text('SELECT 1')).fetchone()
        return {'status': 'healthy', 'connected': True}
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e), 'connected': False}

def optimize_database_settings():
    """Apply production database optimizations"""
    try:
        from sqlalchemy import text
        from app import db
        
        # PostgreSQL specific optimizations
        optimizations = [
            "SET shared_preload_libraries = 'pg_stat_statements'",
            "SET log_statement = 'none'",  # Reduce logging in production
            "SET log_min_duration_statement = 1000",  # Log slow queries only
            "SET checkpoint_completion_target = 0.9",
            "SET wal_buffers = '16MB'",
            "SET effective_cache_size = '1GB'",
        ]
        
        for optimization in optimizations:
            try:
                db.session.execute(text(optimization))
            except Exception as e:
                print(f"Warning: Could not apply optimization '{optimization}': {e}")
        
        db.session.commit()
        print("Database optimizations applied successfully")
        
    except Exception as e:
        print(f"Error applying database optimizations: {e}")
        db.session.rollback()