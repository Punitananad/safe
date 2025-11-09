@echo off
echo Starting CalculatenTrade with fixes...
echo.

REM Set environment to development
set FLASK_ENV=development

REM Run the fixed startup script
python start_app_fixed.py

pause