################################################################################
# RealAgent Complete Installation Script for Windows (PowerShell)
# 
# This script handles the complete setup of RealAgent on a fresh Windows system.
# It will:
#   1. Check Python 3.8+ installation
#   2. Create virtual environment
#   3. Install all dependencies
#   4. Install Playwright browsers
#   5. Initialize database
#   6. Install QR code libraries
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File install.ps1
#   Or right-click and "Run with PowerShell"
#
# For fresh Windows setup, just run this one command!
################################################################################

# Enable colors
$Host.UI.RawUI.ForegroundColor = "White"

# Progress tracking
$TotalSteps = 7
$CurrentStep = 0

# Helper functions
function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([string]$Text)
    $script:CurrentStep++
    Write-Host ""
    Write-Host "[$script:CurrentStep/$TotalSteps]" -ForegroundColor Blue -NoNewline
    Write-Host " $Text..." -ForegroundColor White
}

function Write-Success {
    param([string]$Text)
    Write-Host "✓ $Text" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Text)
    Write-Host "✗ $Text" -ForegroundColor Red
}

function Write-Warning-Custom {
    param([string]$Text)
    Write-Host "⚠ $Text" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Text)
    Write-Host "ℹ $Text" -ForegroundColor Cyan
}

# Start installation
Clear-Host
Write-Header "RealAgent Installation"
Write-Host "This script will set up RealAgent on your Windows PC."
Write-Host "Estimated time: 3-5 minutes"
Write-Host ""
Write-Host "Press any key to continue or Ctrl+C to cancel..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# Step 1: Check Python installation
Write-Step "Checking Python installation"

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Error-Custom "Python is not installed"
    Write-Host ""
    Write-Host "Please install Python 3.8+ from:"
    Write-Host "  • https://www.python.org/downloads/"
    Write-Host ""
    Write-Host "Make sure to check 'Add Python to PATH' during installation!"
    Read-Host "Press Enter to exit"
    exit 1
}

$pythonVersion = (python --version 2>&1) -replace "Python ", ""
$versionParts = $pythonVersion.Split('.')
$majorVersion = [int]$versionParts[0]
$minorVersion = [int]$versionParts[1]

if ($majorVersion -lt 3 -or ($majorVersion -eq 3 -and $minorVersion -lt 8)) {
    Write-Error-Custom "Python 3.8+ required. You have Python $pythonVersion"
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Success "Python $pythonVersion detected"

# Check pip
$pipCmd = Get-Command pip -ErrorAction SilentlyContinue
if (-not $pipCmd) {
    Write-Error-Custom "pip is not installed"
    Read-Host "Press Enter to exit"
    exit 1
}

$pipVersion = (pip --version 2>&1) -replace "pip ", "" -replace " from.*", ""
Write-Success "pip $pipVersion detected"

# Step 2: Create virtual environment
Write-Step "Creating virtual environment"

if (Test-Path ".venv") {
    Write-Warning-Custom "Virtual environment already exists"
    $recreate = Read-Host "Delete and recreate? (y/N)"
    if ($recreate -eq "y" -or $recreate -eq "Y") {
        Remove-Item -Recurse -Force .venv
        python -m venv .venv
        Write-Success "Virtual environment recreated"
    } else {
        Write-Info "Using existing virtual environment"
    }
} else {
    python -m venv .venv
    Write-Success "Virtual environment created"
}

# Step 3: Activate virtual environment
Write-Step "Activating virtual environment"

$activateScript = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    & $activateScript
    Write-Success "Virtual environment activated"
} else {
    Write-Error-Custom "Failed to find activation script"
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 4: Upgrade pip
Write-Step "Upgrading pip"

python -m pip install --upgrade pip --quiet | Out-Null
$pipNewVersion = (pip --version 2>&1) -replace "pip ", "" -replace " from.*", ""
Write-Success "pip upgraded to $pipNewVersion"

# Step 5: Install Python dependencies
Write-Step "Installing Python dependencies"

if (-not (Test-Path "requirements.txt")) {
    Write-Error-Custom "requirements.txt not found!"
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Info "This may take 2-3 minutes..."
pip install -r requirements.txt --quiet

# Install additional QR code libraries
pip install qrcode segno --quiet

Write-Success "All Python dependencies installed"

# Count installed packages
$packageCount = (pip list --format=freeze | Measure-Object -Line).Lines
Write-Info "Total packages installed: $packageCount"

# Step 6: Install Playwright browsers
Write-Step "Installing Playwright browsers"

Write-Info "Downloading Chromium browser (~250MB)..."
Write-Info "This may take 2-3 minutes depending on your connection..."

playwright install chromium

Write-Success "Playwright browsers installed"

# Step 7: Initialize database
Write-Step "Initializing database"

try {
    python -c "from Helper.database import init_mainframe_db; init_mainframe_db()" 2>$null
    
    if (Test-Path "Mainframe.db") {
        $dbSize = (Get-Item "Mainframe.db").Length / 1KB
        $dbSizeFormatted = "{0:N0}" -f $dbSize
        Write-Success "Database initialized (Mainframe.db - $dbSizeFormatted KB)"
    } else {
        Write-Error-Custom "Database initialization failed"
        Write-Warning-Custom "You can initialize it manually later with:"
        Write-Warning-Custom '  python -c "from Helper.database import init_mainframe_db; init_mainframe_db()"'
    }
} catch {
    Write-Error-Custom "Database initialization failed: $_"
}

# Installation complete
Write-Header "Installation Complete!"

Write-Host "✓ RealAgent is ready to use!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 What was installed:" -ForegroundColor Cyan
Write-Host "  • Python virtual environment (.venv\)"
Write-Host "  • $packageCount Python packages"
Write-Host "  • Playwright Chromium browser"
Write-Host "  • SQLite database (Mainframe.db)"
Write-Host ""
Write-Host "🚀 Quick Start:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Activate virtual environment:"
Write-Host "     " -NoNewline
Write-Host ".venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "  2. Run the scraper:"
Write-Host "     " -NoNewline
Write-Host "python Agent.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "  3. Or launch the dashboard:"
Write-Host "     " -NoNewline
Write-Host "python Dashboard.py" -ForegroundColor Yellow
Write-Host "     Then open: http://localhost:5000"
Write-Host ""
Write-Host "📚 Documentation:" -ForegroundColor Cyan
Write-Host "  • README.md - Full documentation"
Write-Host "  • INSTALLATION_COMPLETE.md - Setup summary"
Write-Host "  • QUICKSTART.md - Quick reference"
Write-Host ""
Write-Host "💡 Tip: If you get execution policy errors, run:" -ForegroundColor Cyan
Write-Host "  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser"
Write-Host ""
Write-Host "Happy scraping! 🏠" -ForegroundColor Green
Write-Host ""

# Deactivate virtual environment
deactivate 2>$null

Read-Host "Press Enter to exit"
