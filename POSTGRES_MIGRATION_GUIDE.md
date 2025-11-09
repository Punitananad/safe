# SQLite to PostgreSQL Migration Guide

This guide will help you migrate your CalculatenTrade application from SQLite to PostgreSQL.

## Prerequisites

1. **PostgreSQL installed and running**
   - Download from: https://www.postgresql.org/download/windows/
   - Remember the password you set for the `postgres` user during installation

2. **Python packages**
   ```bash
   pip install psycopg2-binary
   ```

## Migration Steps

### Option 1: Automated Migration (Recommended)

1. **Run the migration batch file:**
   ```cmd
   migrate_to_postgres.bat
   ```
   
   This will:
   - Install required packages
   - Set up PostgreSQL database and user
   - Migrate all data from SQLite to PostgreSQL
   - Update your .env file

### Option 2: Manual Migration

#### Step 1: Setup PostgreSQL Database

1. **Edit `setup_postgres.py`:**
   - Update the `ADMIN_CONFIG['password']` with your PostgreSQL admin password

2. **Run the setup script:**
   ```bash
   python setup_postgres.py
   ```

#### Step 2: Migrate Data

1. **Run the migration script:**
   ```bash
   python migrate_to_postgres.py
   ```

#### Step 3: Update Configuration

1. **Update your `.env` file:**
   ```env
   DATABASE_TYPE=postgres
   ```

2. **Add PostgreSQL connection details (if different from defaults):**
   ```env
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=calculatentrade_db
   DB_USER=cnt_user
   DB_PASSWORD=CNT_SecurePass_2024!
   ```

## Database Configuration

The migration creates:

- **Database:** `calculatentrade_db`
- **User:** `cnt_user`
- **Password:** `CNT_SecurePass_2024!`

## Tables Migrated

### Main Application Tables (calculatentrade.db)
- `users` - User accounts and authentication
- `intraday_trades` - Intraday trading calculations
- `delivery_trades` - Delivery trading calculations
- `swing_trades` - Swing trading calculations
- `mtf_trades` - MTF trading calculations
- `fo_trades` - F&O trading calculations
- `payments` - Payment records
- `coupon_usage` - Coupon usage tracking
- `trade_splits` - Position splitting data
- `preview_templates` - Saved templates
- `ai_plan_templates` - AI plan templates
- All OTP and settings tables

### Journal Tables (database.db)
- `trades` - Trading journal entries
- `strategies` - Trading strategies
- `mistakes` - Trading mistakes log
- `rules` - Trading rules

## Verification Steps

1. **Start your Flask application:**
   ```bash
   python app.py
   ```

2. **Check the logs for:**
   ```
   Using PostgreSQL database
   ```

3. **Verify data migration:**
   - Login to your application
   - Check that all your saved trades are present
   - Verify user accounts and settings
   - Test journal functionality

4. **Test all features:**
   - Calculator functions
   - Saving trades
   - User authentication
   - Journal entries

## Troubleshooting

### Connection Issues

1. **PostgreSQL not running:**
   ```bash
   # Windows - Start PostgreSQL service
   net start postgresql-x64-14
   ```

2. **Authentication failed:**
   - Verify PostgreSQL admin password
   - Check if user was created successfully

3. **Database connection errors:**
   - Verify PostgreSQL is listening on port 5432
   - Check firewall settings

### Migration Issues

1. **Tables not found:**
   - Ensure SQLite databases exist in `instance/` folder
   - Check file paths in migration script

2. **Data type errors:**
   - Review migration logs for specific errors
   - Some data types may need manual conversion

3. **Foreign key constraints:**
   - Migration script handles this automatically
   - Check for orphaned records if issues occur

## Rollback Procedure

If you need to rollback to SQLite:

1. **Restore .env file:**
   ```bash
   copy .env.backup .env
   ```

2. **Restart your application**

Your original SQLite databases remain unchanged during migration.

## Performance Benefits

After migration to PostgreSQL, you'll experience:

- **Better concurrent user support**
- **Improved query performance**
- **Better data integrity**
- **Advanced indexing capabilities**
- **Full-text search capabilities**
- **Better backup and recovery options**

## Security Notes

- Change the default PostgreSQL password in production
- Use environment variables for database credentials
- Enable SSL connections for production deployments
- Regular database backups are recommended

## Support

If you encounter issues:

1. Check the migration logs for specific errors
2. Verify PostgreSQL installation and configuration
3. Ensure all prerequisites are met
4. Review the troubleshooting section above

The migration preserves all your existing data while providing the benefits of a production-ready database system.