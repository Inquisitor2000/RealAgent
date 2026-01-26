@echo off
setlocal enabledelayedexpansion
REM ===================================================
REM  RealAgent Dashboard Launcher
REM  Starts the Flask dashboard and opens it in Edge
REM  Path-agnostic version - works from any location
REM ===================================================

echo.
echo ================================================
echo    RealAgent Dashboard Launcher
echo ================================================
echo.

REM Change to the directory where this batch file is located
cd /d "%~dp0"

echo [*] Verifying project setup...
echo Current directory: %CD%
echo.

REM Verify project structure
set VERIFICATION_FAILED=0

echo Checking project files:
if exist "Dashboard.py" (
    echo [OK] Dashboard.py found
) else (
    echo [ERROR] Dashboard.py missing
    set VERIFICATION_FAILED=1
)

if exist "Agent.py" (
    echo [OK] Agent.py found
) else (
    echo [ERROR] Agent.py missing
    set VERIFICATION_FAILED=1
)

if exist "requirements.txt" (
    echo [OK] requirements.txt found
) else (
    echo [ERROR] requirements.txt missing
    set VERIFICATION_FAILED=1
)

if exist "Helper" (
    echo [OK] Helper directory found
) else (
    echo [ERROR] Helper directory missing
    set VERIFICATION_FAILED=1
)

if exist "Templates" (
    echo [OK] Templates directory found
) else (
    echo [ERROR] Templates directory missing
    set VERIFICATION_FAILED=1
)

if exist "Mainframe.db" (
    echo [OK] Mainframe.db found
) else (
    echo [INFO] Mainframe.db not found ^(will be created by Agent.py^)
)

if exist "Listings" (
    echo [OK] Listings directory found
) else (
    echo [INFO] Listings directory not found ^(will be created automatically^)
)

echo.

if !VERIFICATION_FAILED! == 1 (
    echo [ERROR] Project verification failed - critical files missing
    echo Please ensure this batch file is in the correct RealAgent project folder
    pause
    exit /b 1
)

echo [SUCCESS] Project structure verified successfully!
echo.

echo Checking Python installation:
REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found in PATH, checking alternatives...
    echo.
    
    REM Try py command (Python Launcher)
    py --version >nul 2>&1
    if errorlevel 1 (
        REM Try common Python installation locations
        if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
            echo [OK] Python 3.13 found in Local Programs
            set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
            goto :python_found
        )
        if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
            echo [OK] Python 3.12 found in Local Programs
            set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
            goto :python_found
        )
        if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
            echo [OK] Python 3.11 found in Local Programs
            set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
            goto :python_found
        )
        if exist "C:\Python313\python.exe" (
            echo [OK] Python 3.13 found in C:\Python313
            set PYTHON_CMD="C:\Python313\python.exe"
            goto :python_found
        )
        if exist "C:\Python312\python.exe" (
            echo [OK] Python 3.12 found in C:\Python312
            set PYTHON_CMD="C:\Python312\python.exe"
            goto :python_found
        )
        if exist "C:\Python311\python.exe" (
            echo [OK] Python 3.11 found in C:\Python311
            set PYTHON_CMD="C:\Python311\python.exe"
            goto :python_found
        )
        if exist ".venv\Scripts\python.exe" (
            echo [OK] Python found in virtual environment
            set PYTHON_CMD=.venv\Scripts\python.exe
            goto :python_found
        )
        
        echo [ERROR] Python is not available
        echo.
        echo Searched locations:
        echo - System PATH
        echo - Python Launcher ^(py command^)
        echo - %LOCALAPPDATA%\Programs\Python\
        echo - C:\Python3xx\
        echo - Virtual environment ^(.venv\Scripts\python.exe^)
        echo.
        echo Please either:
        echo 1. Install Python from https://python.org and add to PATH
        echo 2. Create a virtual environment with: python -m venv .venv
        echo 3. Or ensure Python is installed in a standard location
        pause
        exit /b 1
    ) else (
        echo [OK] Python found via 'py' command
        set PYTHON_CMD=py
    )
) else (
    echo [OK] Python found via 'python' command
    set PYTHON_CMD=python
)

:python_found
echo.
echo Checking Python dependencies:
%PYTHON_CMD% -c "import flask" 2>nul
if errorlevel 1 (
    echo [WARNING] Flask not found, attempting to install dependencies...
    echo Installing requirements from requirements.txt...
    %PYTHON_CMD% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        echo Please run: %PYTHON_CMD% -m pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo [SUCCESS] Dependencies installed successfully
) else (
    echo [OK] Flask is available
)

echo.
echo [SUCCESS] All verifications passed! Starting dashboard...
echo.

echo Starting Flask server...
echo Dashboard will open at: http://localhost:5000
echo Project directory: %CD%
echo.
echo Press Ctrl+C to stop the server
echo ================================================
echo.

REM Wait 2 seconds then open Microsoft Edge
start /B cmd /c "timeout /t 2 /nobreak >nul && start msedge http://localhost:5000"

REM Start the Flask server using the detected Python command
%PYTHON_CMD% Dashboard.py

REM If the server stops, pause to see any error messages
echo.
echo ================================================
echo Server stopped. Press any key to exit...
pause
