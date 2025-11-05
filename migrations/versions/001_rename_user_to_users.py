"""rename user->users and update fks

Revision ID: 001_rename_user_to_users
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_rename_user_to_users'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Rename user table to users
    op.rename_table('user', 'users')
    
    # Update foreign key constraints - PostgreSQL automatically updates FK references
    # when the referenced table is renamed, but we'll be explicit about constraint names
    
    # The following constraints will be automatically updated by PostgreSQL:
    # - user_settings.user_id -> users.id
    # - intraday_trades.user_id -> users.id  
    # - delivery_trades.user_id -> users.id
    # - swing_trades.user_id -> users.id
    # - mtf_trades.user_id -> users.id
    # - fo_trades.user_id -> users.id
    # - preview_templates.user_id -> users.id
    # - ai_plan_templates.user_id -> users.id


def downgrade():
    # Rename users table back to user
    op.rename_table('users', 'user')
    
    # Foreign key constraints will be automatically updated back by PostgreSQL