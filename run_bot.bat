@echo off

echo.
echo ==========================================
echo    Telegram Bot Starter
echo ==========================================
echo.

rem 1. Check if Python is installed in the system
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! 
    echo Please install Python and check 'Add Python to PATH' during installation.
    pause
    exit /b
)

rem 2. Setup VENV paths
set "V_PATH=%~dp0venv"
set "V_PYTHON=%~dp0venv\Scripts\python.exe"
set "V_PIP=%~dp0venv\Scripts\pip.exe"

rem 3. Heal broken venv
if not exist "%V_PATH%" goto create_venv

echo [INFO] Checking virtual environment...
"%V_PYTHON%" --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Environment is broken. Removing...
    rd /s /q "%V_PATH%"
)

:create_venv
rem 4. Create venv if needed
if exist "%V_PATH%" goto run_bot

echo [INFO] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Could not create venv.
    pause
    exit /b
)
echo [INFO] Updating pip and installing libraries...
"%V_PIP%" install --upgrade pip
"%V_PIP%" install -r requirements.txt
"%V_PYTHON%" -m playwright install chromium

:run_bot
rem 5. Run the Bot
echo [INFO] Starting bot.py...
echo.
"%V_PYTHON%" bot.py

if errorlevel 1 (
    echo.
    echo [ERROR] Bot stopped with an error!
) else (
    echo.
    echo [SUCCESS] Bot finished work.
)

pause
