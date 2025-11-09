@echo off
echo Starting CalculatenTrade Flask App...
echo.

REM Set environment variables
set FLASK_APP=app.py
set FLASK_ENV=development

REM Run Flask using CLI (recommended way)
echo Using Flask CLI to start the application...
flask run --host=0.0.0.0 --port=5000 --debug

pause