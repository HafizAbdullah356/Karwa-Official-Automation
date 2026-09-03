@echo off
echo ====================================================
echo Setting up Karwa Qatar Mobile Automation environment
echo ====================================================
echo.

:: Check Python
set "PYTHON_EXE=python"
%PYTHON_EXE% --version >nul 2>&1
if %errorlevel% neq 0 (
    if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
        set "PYTHON_EXE=%LOCALAPPDATA%\Python\bin\python.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    ) else (
        echo [ERROR] Python is not installed or not in system PATH.
        echo Please install Python from python.org and try again.
        pause
        exit /b 1
    )
)

:: Create Virtual Environment
if not exist venv (
    echo Creating Python virtual environment...
    "%PYTHON_EXE%" -m venv venv
) else (
    echo Virtual environment already exists.
)

:: Activate and install dependencies
echo.
echo Installing dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ====================================================
echo Setup Completed Successfully!
echo ====================================================
echo.
echo 1. Connect your phone to the same Wi-Fi network as this PC.
echo 2. Enable Developer Options on your phone:
echo    - Go to Settings -> About Phone -> Tap "Build Number" 7 times.
echo 3. Enable Wireless Debugging:
echo    - Go to Settings -> Developer Options -> Turn on "Wireless Debugging".
echo    - Note down the IP address and Port (e.g. 192.168.1.100:5555).
echo 4. Open "config.json" in this folder and put the IP:Port in "adb_target_ip".
echo 5. Run "run.bat" to start the automation.
echo.
pause
