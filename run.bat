@echo off
echo ====================================================
echo Starting Karwa Qatar Mobile Automation Runner
echo ====================================================
echo.

if not exist venv (
    echo [ERROR] Virtual environment 'venv' not found. Please run setup.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
venv\Scripts\python.exe automation.py
pause
