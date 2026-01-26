# 🛠️ RealAgent Setup Scripts

This folder contains installation scripts for different operating systems.

## 📁 Files

- **`install.sh`** - Bash script for macOS and Linux
- **`install.bat`** - Batch script for Windows (Command Prompt)
- **`install.ps1`** - PowerShell script for Windows (PowerShell)
- **`INSTALLATION_COMPLETE.md`** - Post-installation summary

## 🚀 Usage

### macOS / Linux

```bash
bash setup/install.sh
```

### Windows (Command Prompt)

```cmd
setup\install.bat
```

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File setup\install.ps1
```

## ✨ What the Installer Does

1. ✅ Checks Python 3.8+ installation
2. ✅ Creates virtual environment (`.venv/`)
3. ✅ Upgrades pip to latest version
4. ✅ Installs all Python dependencies from `requirements.txt`
5. ✅ Installs QR code libraries (`qrcode`, `segno`)
6. ✅ Installs Playwright Chromium browser (~250MB)
7. ✅ Initializes SQLite database (`Mainframe.db`)

## 📊 Installation Time

- **Fast connection**: 3-5 minutes
- **Slow connection**: 5-10 minutes (Playwright download is ~250MB)

## 🔧 Requirements

### All Platforms
- Python 3.8 or higher
- pip (Python package manager)
- Internet connection

### Windows Additional
- Git for Windows (for `git clone`)
- PowerShell 5.0+ (for `.ps1` script)

### macOS Additional
- Xcode Command Line Tools (usually pre-installed)

## 🐛 Troubleshooting

### Python Not Found

**macOS/Linux:**
```bash
# Install Python via Homebrew (macOS)
brew install python3

# Or download from python.org
```

**Windows:**
- Download from https://www.python.org/downloads/
- **Important**: Check "Add Python to PATH" during installation

### Permission Denied (macOS/Linux)

```bash
chmod +x setup/install.sh
bash setup/install.sh
```

### Execution Policy Error (Windows PowerShell)

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then run the installer again.

### Virtual Environment Already Exists

The installer will ask if you want to recreate it. Choose:
- **Yes (y)**: Delete and create fresh environment
- **No (n)**: Use existing environment

## 📝 Manual Installation

If you prefer to install manually, see the main [README.md](../README.md) for step-by-step instructions.

## 🔄 Reinstalling

To reinstall from scratch:

1. Delete the virtual environment:
   ```bash
   rm -rf .venv  # macOS/Linux
   rmdir /s .venv  # Windows
   ```

2. Delete the database (optional):
   ```bash
   rm Mainframe.db  # macOS/Linux
   del Mainframe.db  # Windows
   ```

3. Run the installer again

## 📚 After Installation

Once installation is complete, see:
- **`INSTALLATION_COMPLETE.md`** - What was installed
- **`../README.md`** - Full documentation
- **`../QUICKSTART.md`** - Quick reference guide

## 💡 Tips

### Create Desktop Shortcuts

**Windows:**
1. Right-click `setup\install.bat`
2. Send to → Desktop (create shortcut)

**macOS:**
1. Create an Automator application
2. Add "Run Shell Script" action
3. Paste: `cd /path/to/RealAgent && bash setup/install.sh`

### Alias for Quick Access

**macOS/Linux** (`~/.zshrc` or `~/.bashrc`):
```bash
alias realagent-install="cd ~/path/to/RealAgent && bash setup/install.sh"
```

**Windows PowerShell** (`$PROFILE`):
```powershell
function Install-RealAgent { 
    cd C:\path\to\RealAgent
    & .\setup\install.ps1 
}
```

---

**Need help?** Open an issue on GitHub or check the main README.md
