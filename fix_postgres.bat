@echo off
echo Setting up PostgreSQL for CalculatenTrade...

echo.
echo 1. Make sure PostgreSQL is running
echo 2. Run this as administrator if needed
echo.

echo Creating database and user...
psql -U postgres -c "CREATE DATABASE calculatentrade_db;"
psql -U postgres -c "CREATE USER cnt_user WITH PASSWORD 'CNT_SecurePass_2024!';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE calculatentrade_db TO cnt_user;"
psql -U postgres -d calculatentrade_db -c "GRANT ALL ON SCHEMA public TO cnt_user;"

echo.
echo Setup complete! Now update your .env file:
echo FLASK_ENV=production
echo DATABASE_TYPE=postgres
echo.
pause