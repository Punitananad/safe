"""Add email verification system

Revision ID: add_email_verification_system
Revises: 9e21f2041e97
Create Date: 2024-11-09 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_email_verification_system'
down_revision = '9e21f2041e97'
branch_labels = None
depends_on = None


def upgrade():
    # Create users table if it doesn't exist
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(255),
            coupon_code VARCHAR(50),
            registered_on TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            verified BOOLEAN NOT NULL DEFAULT FALSE,
            google_id VARCHAR(100) UNIQUE,
            profile_pic VARCHAR(200),
            name VARCHAR(100),
            subscription_active BOOLEAN NOT NULL DEFAULT FALSE,
            subscription_expires TIMESTAMP WITH TIME ZONE,
            subscription_type VARCHAR(20)
        );
    """)
    
    # Create index on email if it doesn't exist
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);")
    
    # Create reset_otp table if it doesn't exist
    op.execute("""
        CREATE TABLE IF NOT EXISTS reset_otp (
            id SERIAL PRIMARY KEY,
            email VARCHAR(120) NOT NULL,
            otp_hash VARCHAR(128) NOT NULL,
            salt VARCHAR(64) NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            used BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
    """)
    
    # Create indexes for reset_otp
    op.execute("CREATE INDEX IF NOT EXISTS ix_reset_otp_email ON reset_otp (email);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reset_otp_expires_at ON reset_otp (expires_at);")
    
    # Create email_verify_otp table if it doesn't exist
    op.execute("""
        CREATE TABLE IF NOT EXISTS email_verify_otp (
            id SERIAL PRIMARY KEY,
            email VARCHAR(120) NOT NULL,
            otp_hash VARCHAR(128) NOT NULL,
            salt VARCHAR(64) NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            used BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
    """)
    
    # Create indexes for email_verify_otp
    op.execute("CREATE INDEX IF NOT EXISTS ix_email_verify_otp_email ON email_verify_otp (email);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_email_verify_otp_expires_at ON email_verify_otp (expires_at);")
    
    # Create delete_account_otp table if it doesn't exist
    op.execute("""
        CREATE TABLE IF NOT EXISTS delete_account_otp (
            id SERIAL PRIMARY KEY,
            email VARCHAR(120) NOT NULL,
            otp_hash VARCHAR(128) NOT NULL,
            salt VARCHAR(64) NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            used BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
    """)
    
    # Create indexes for delete_account_otp
    op.execute("CREATE INDEX IF NOT EXISTS ix_delete_account_otp_email ON delete_account_otp (email);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_delete_account_otp_expires_at ON delete_account_otp (expires_at);")
    
    # Create user_settings table if it doesn't exist
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            email_notifications BOOLEAN DEFAULT TRUE,
            theme VARCHAR(20) DEFAULT 'light',
            timezone VARCHAR(50) DEFAULT 'Asia/Kolkata',
            default_calculator VARCHAR(20) DEFAULT 'intraday',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)
    
    # Ensure verified column exists and has correct default
    op.execute("""
        ALTER TABLE users 
        ALTER COLUMN verified SET DEFAULT FALSE;
    """)
    
    print("Email verification system tables created successfully!")


def downgrade():
    # Drop tables in reverse order
    op.drop_table('user_settings', if_exists=True)
    op.drop_table('delete_account_otp', if_exists=True)
    op.drop_table('email_verify_otp', if_exists=True)
    op.drop_table('reset_otp', if_exists=True)
    # Note: Not dropping users table as it may contain important data