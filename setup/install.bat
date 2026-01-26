@echo off
REM ################################################################################
REM RealAgent Complete Installation Script for Windows
REM 
REM This script handles the complete setup of RealAgent on a fresh Windows system.
REM It will:
REM   1. Check Python 3.8+ installation
REM   2. Create virtual environment
REM   3. Install all dependencies
REM   4. Install Playwright browsers
REM   5. Initialize database
REM   6. Install QR code libraries
REM
REM Usage:
REM   install.bat
REM
REM For fresh Windows setup, just run this one command!
REM ################################################################################

setlocal enabledelayedexpansion

REM Colors using ANSI escape codes (Windows 10+)
set "GREEN=[92m"
set "RED=[91m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "CYAN=[96m"
set "NC=[0m"

REM Progress tracking
set TOTAL_STEPS=7
set CURRENT_STEP=0

REM Clear screen
cls

echo.
echo %CYAN%==========================================
echo   RealAgent Installation
echo ==========================================%NC%
echo.
echo This script will set up RealAgent on your Windows PC.
echo Estimated time: 3-5 minutes
echo.
pause

REM Step 1: Check Python installation
set /a CURRENT_STEP+=1
echo.
echo %BLUE%[%CURRENT_STEP%/%TOTAL_STEPS%]%NC% Checking Python installation...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%X Python is not installed%NC%
    echo.
    echo Please install Python 3.8+ from:
    echo   * https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation!
    pause
    exit /b 1
)

REM Get Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i

REM Extract major and minor version
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set PYTHON_MAJOR=%%a
    set PYTHON_MINOR=%%b
)

REM Check if Python version is 3.8+
if %PYTHON_MAJOR% lss 3 (
    echo %RED%X Python 3.8+ required. You have Python %PYTHON_VERSION%%NC%
    pause
    exit /b 1
)
if %PYTHON_MAJOR% equ 3 if %PYTHON_MINOR% lss 8 (
    echo %RED%X Python 3.8+ required. You have Python %PYTHON_VERSION%%NC%
    pause
    exit /b 1
)

echo %GREEN%√ Python %PYTHON_VERSION% detected%NC%

REM Check pip
where pip >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%X pip is not installed%NC%
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('pip --version 2^>^&1') do set PIP_VERSION=%%i
echo %GREEN%√ pip %PIP_VERSION% detected%NC%

REM Step 2: Create virtual environment
set /a CURRENT_STEP+=1
echo.
echo %BLUE%[%CURRENT_STEP%/%TOTAL_STEPS%]%NC% Creating virtual environment...

if exist ".venv" (
    echo %YELLOW%! Virtual environment already exists%NC%
    set /p "RECREATE=Delete and recreate? (y/N): "
    if /i "!RECREATE!"=="y" (
        rmdir /s /q .venv
        python -m venv .venv
        echo %GREEN%√ Virtual environment recreated%NC%
    ) else (
        echo %CYAN%i Using existing virtual environment%NC%
    )
) else (
    python -m venv .venv
    echo %GREEN%√ Virtual environment created%NC%
)

REM Step 3: Activate virtual environment
set /a CURRENT_STEP+=1
echo.
echo %BLUE%[%CURRENT_STEP%/%TOTAL_STEPS%]%NC% Activating virtual environment...

call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo %RED%X Failed to activate virtual environment%NC%
    pause
    exit /b 1
)

echo %GREEN%√ Virtual environment activated%NC%

REM Step 4: Upgrade pip
set /a CURRENT_STEP+=1
echo.
echo %BLUE%[%CURRENT_STEP%/%TOTAL_STEPS%]%NC% Upgrading pip...

python -m pip install --upgrade pip --quiet
for /f "tokens=2" %%i in ('pip --version 2^>^&1') do set PIP_NEW_VERSION=%%i
echo %GREEN%√ pip upgraded to %PIP_NEW_VERSION%%NC%

REM Step 5: Install Python dependencies
set /a CURRENT_STEP+=1
echo.
echo %BLUE%[%CURRENT_STEP%/%TOTAL_STEPS%]%NC% Installing Python dependencies...

if not exist "requirements.txt" (
    echo %RED%X requirements.txt not found!%NC%
    pause
    exit /b 1
)

echo %CYAN%i This may take 2-3 minutes...%NC%
pip install -r requirements.txt --quiet

REM Install additional QR code libraries
pip install qrcode segno --quiet

echo %GREEN%√ All Python dependencies installed%NC%

REM Count installed packages
for /f %%i in ('pip list --format^=freeze ^| find /c /v ""') do set PACKAGE_COUNT=%%i
echo %CYAN%i Total packages installed: %PACKAGE_COUNT%%NC%

REM Step 6: Install Playwright browsers
set /a CURRENT_STEP+=1
echo.
echo %BLUE%[%CURRENT_STEP%/%TOTAL_STEPS%]%NC% Installing Playwright browsers...

echo %CYAN%i Downloading Chromium browser (~250MB)...%NC%
echo %CYAN%i This may take 2-3 minutes depending on your connection...%NC%

playwright install chromium

echo %GREEN%√ Playwright browsers installed%NC%

REM Step 7: Initialize database
set /a CURRENT_STEP+=1
echo.
echo %BLUE%[%CURRENT_STEP%/%TOTAL_STEPS%]%NC% Initializing database...

python -c "from Helper.database import init_mainframe_db; init_mainframe_db()" 2>nul

if exist "Mainframe.db" (
    for %%A in (Mainframe.db) do set DB_SIZE=%%~zA
    set /a DB_SIZE_KB=!DB_SIZE! / 1024
    echo %GREEN%√ Database initialized (Mainframe.db - !DB_SIZE_KB! KB)%NC%
) else (
    echo %RED%X Database initialization failed%NC%
    echo %YELLOW%! You can initialize it manually later with:%NC%
    echo   python -c "from Helper.database import init_mainframe_db; init_mainframe_db()"
)

REM Installation complete
echo.
echo %CYAN%==========================================
echo   Installation Complete!
echo ==========================================%NC%
echo.
echo %GREEN%√ RealAgent is ready to use!%NC%
echo.
echo %CYAN%What was installed:%NC%
echo   * Python virtual environment (.venv\)
echo   * %PACKAGE_COUNT% Python packages
echo   * Playwright Chromium browser
echo   * SQLite database (Mainframe.db)
echo.
echo %CYAN%Quick Start:%NC%
echo.
echo   1. Activate virtual environment:
echo      %YELLOW%.venv\Scripts\activate%NC%
echo.
echo   2. Run the scraper:
echo      %YELLOW%python Agent.py%NC%
echo.
echo   3. Or launch the dashboard:
echo      %YELLOW%python Dashboard.py%NC%
echo      Then open: http://localhost:5000
echo.
echo %CYAN%Documentation:%NC%
echo   * README.md - Full documentation
echo   * INSTALLATION_COMPLETE.md - Setup summary
echo   * QUICKSTART.md - Quick reference
echo.
echo %CYAN%Tip:%NC% Create a shortcut to activate.bat for easy access:
echo   .venv\Scripts\activate.bat
echo.
echo %GREEN%Happy scraping! 🏠%NC%
echo.

REM Deactivate virtual environment
call .venv\Scripts\deactivate.bat 2>nul

pause
