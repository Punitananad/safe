@echo off
echo Starting PostgreSQL migration...
echo.

echo Step 1: Creating PostgreSQL schema...
python create_postgres_schema.py
if %errorlevel% neq 0 (
    echo Schema creation failed!
    pause
    exit /b 1
)

echo.
echo Step 2: Migrating data from SQLite to PostgreSQL...
python migrate_to_postgres.py
if %errorlevel% neq 0 (
    echo Data migration failed!
    pause
    exit /b 1
)

echo.
echo Step 3: Running Flask database migrations...
flask db upgrade
if %errorlevel% neq 0 (
    echo Flask migration failed!
    pause
    exit /b 1
)

echo.
echo PostgreSQL migration completed successfully!
echo All databases are now using PostgreSQL.
echo.
pause