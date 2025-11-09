@echo off
echo ========================================
echo   CalculatenTrade Safe Startup
echo ========================================
echo.

REM Set environment to development
set FLASK_ENV=development

REM Run the safe startup script
python start_safe.py

echo.
echo ========================================
echo   Startup Complete
echo ========================================
pause