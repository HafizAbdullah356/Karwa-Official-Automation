@echo off
echo ====================================================
echo Starting FARWAN QATAR Modern GUI Application...
echo ====================================================
echo.

if not exist venv (
    echo [ERROR] Virtual environment 'venv' not found. Please run setup.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
start "" venv\Scripts\pythonw.exe gui.py
