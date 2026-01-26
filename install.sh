#!/bin/bash
################################################################################
# RealAgent Complete Installation Script
# 
# This script handles the complete setup of RealAgent on a fresh macOS system.
# It will:
#   1. Check Python 3.8+ installation
#   2. Create virtual environment
#   3. Install all dependencies
#   4. Install Playwright browsers
#   5. Initialize database
#   6. Install QR code libraries
#
# Usage:
#   bash install.sh
#
# For fresh Mac setup, just run this one command!
################################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Progress tracking
TOTAL_STEPS=7
CURRENT_STEP=0

# Helper functions
print_header() {
    echo ""
    echo -e "${CYAN}=========================================="
    echo -e "  $1"
    echo -e "==========================================${NC}"
    echo ""
}

print_step() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo ""
    echo -e "${BLUE}[$CURRENT_STEP/$TOTAL_STEPS]${NC} $1..."
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

# Start installation
clear
print_header "RealAgent Installation"
echo "This script will set up RealAgent on your Mac."
echo "Estimated time: 3-5 minutes"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

# Step 1: Check Python installation
print_step "Checking Python installation"

if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed"
    echo ""
    echo "Please install Python 3.8+ from:"
    echo "  • https://www.python.org/downloads/"
    echo "  • Or use Homebrew: brew install python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    print_error "Python 3.8+ required. You have Python $PYTHON_VERSION"
    exit 1
fi

print_success "Python $PYTHON_VERSION detected"

# Check pip3
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 is not installed"
    exit 1
fi

PIP_VERSION=$(pip3 --version 2>&1 | cut -d' ' -f2)
print_success "pip $PIP_VERSION detected"

# Step 2: Create virtual environment
print_step "Creating virtual environment"

if [ -d ".venv" ]; then
    print_warning "Virtual environment already exists"
    read -p "Delete and recreate? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf .venv
        python3 -m venv .venv
        print_success "Virtual environment recreated"
    else
        print_info "Using existing virtual environment"
    fi
else
    python3 -m venv .venv
    print_success "Virtual environment created"
fi

# Step 3: Activate virtual environment
print_step "Activating virtual environment"

source .venv/bin/activate

if [ -z "$VIRTUAL_ENV" ]; then
    print_error "Failed to activate virtual environment"
    exit 1
fi

print_success "Virtual environment activated"

# Step 4: Upgrade pip
print_step "Upgrading pip"

python -m pip install --upgrade pip --quiet
PIP_NEW_VERSION=$(pip --version 2>&1 | cut -d' ' -f2)
print_success "pip upgraded to $PIP_NEW_VERSION"

# Step 5: Install Python dependencies
print_step "Installing Python dependencies"

if [ ! -f "requirements.txt" ]; then
    print_error "requirements.txt not found!"
    exit 1
fi

print_info "This may take 2-3 minutes..."
pip install -r requirements.txt --quiet

# Install additional QR code libraries
pip install qrcode segno --quiet

print_success "All Python dependencies installed"

# Show installed packages count
PACKAGE_COUNT=$(pip list --format=freeze | wc -l | tr -d ' ')
print_info "Total packages installed: $PACKAGE_COUNT"

# Step 6: Install Playwright browsers
print_step "Installing Playwright browsers"

print_info "Downloading Chromium browser (~250MB)..."
print_info "This may take 2-3 minutes depending on your connection..."

playwright install chromium

print_success "Playwright browsers installed"

# Step 7: Initialize database
print_step "Initializing database"

python -c "from Helper.database import init_mainframe_db; init_mainframe_db()" 2>/dev/null

if [ -f "Mainframe.db" ]; then
    DB_SIZE=$(ls -lh Mainframe.db | awk '{print $5}')
    print_success "Database initialized (Mainframe.db - $DB_SIZE)"
else
    print_error "Database initialization failed"
    print_warning "You can initialize it manually later with:"
    print_warning "  python -c \"from Helper.database import init_mainframe_db; init_mainframe_db()\""
fi

# Installation complete
print_header "Installation Complete!"

echo -e "${GREEN}✅ RealAgent is ready to use!${NC}"
echo ""
echo "📋 What was installed:"
echo "  • Python virtual environment (.venv/)"
echo "  • $PACKAGE_COUNT Python packages"
echo "  • Playwright Chromium browser"
echo "  • SQLite database (Mainframe.db)"
echo ""
echo "🚀 Quick Start:"
echo ""
echo "  1. Activate virtual environment:"
echo -e "     ${CYAN}source .venv/bin/activate${NC}"
echo ""
echo "  2. Run the scraper:"
echo -e "     ${CYAN}python Agent.py${NC}"
echo ""
echo "  3. Or launch the dashboard:"
echo -e "     ${CYAN}python Dashboard.py${NC}"
echo "     Then open: http://localhost:5000"
echo ""
echo "📚 Documentation:"
echo "  • README.md - Full documentation"
echo "  • INSTALLATION_COMPLETE.md - Setup summary"
echo ""
echo "💡 Tip: Add these aliases to ~/.zshrc for convenience:"
echo "  alias python=python3"
echo "  alias pip=pip3"
echo ""
echo -e "${GREEN}Happy scraping! 🏠${NC}"
echo ""

# Deactivate virtual environment
deactivate 2>/dev/null || true
