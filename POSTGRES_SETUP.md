    # PostgreSQL Migration - Complete Setup

    Your SQLite data has been exported and your application is configured for PostgreSQL.

    ## What's Done ✅

    1. **Environment Updated** - `.env` file now uses PostgreSQL
    2. **Data Exported** - SQLite data exported to SQL files
    3. **Scripts Created** - All migration scripts ready

    ## Next Steps

    ### 1. Install PostgreSQL

    Download and install PostgreSQL from: https://www.postgresql.org/download/windows/

    **During installation:**
    - Remember the password for `postgres` user
    - Use default port `5432`
    - Install pgAdmin (optional but recommended)

    ### 2. Create Database

    Open Command Prompt as Administrator and run:

    ```cmd
    # Connect to PostgreSQL
    psql -U postgres -h localhost

    # In PostgreSQL prompt:
    CREATE DATABASE calculatentrade_db;
    CREATE USER cnt_user WITH PASSWORD 'CNT_SecurePass_2024!';
    GRANT ALL PRIVILEGES ON DATABASE calculatentrade_db TO cnt_user;
    \q
    ```

    ### 3. Create Tables

    ```cmd
    # Connect to your database
    psql -U cnt_user -d calculatentrade_db -h localhost

    # Run the table creation script
    \i create_postgres_tables.sql
    \q
    ```

    ### 4. Import Data

    ```cmd
    # Import main database data
    psql -U cnt_user -d calculatentrade_db -h localhost -f calculatentrade_export.sql

    # Import journal data
    psql -U cnt_user -d calculatentrade_db -h localhost -f journal_export.sql
    ```

    ### 5. Start Your Application

    ```cmd
    python app.py
    ```

    You should see: `Using PostgreSQL database`

    ## Files Created

    - `create_postgres_tables.sql` - Creates all tables
    - `calculatentrade_export.sql` - Your main app data
    - `journal_export.sql` - Your journal data
    - `.env.backup` - Backup of original settings

    ## Troubleshooting

    **Connection Issues:**
    - Ensure PostgreSQL service is running
    - Check Windows Firewall settings
    - Verify port 5432 is open

    **Permission Issues:**
    - Run Command Prompt as Administrator
    - Check user permissions in PostgreSQL

    **Data Issues:**
    - Your original SQLite files are unchanged
    - You can revert by restoring `.env.backup`

    ## Verification

    After setup, test these features:
    - User login
    - Calculator functions
    - Saved trades
    - Journal entries

    Your migration is complete! 🎉