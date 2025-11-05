@echo off
echo Setting up PostgreSQL database...
"C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -f setup_postgres.sql
pause