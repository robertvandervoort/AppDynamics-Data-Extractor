@echo off
REM AppDynamics Data Extractor - Modular Version
REM This script sets up and runs the modular version of the AppDynamics Data Extractor

echo 🚀 Starting AppDynamics Data Extractor (Modular Version)

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed. Please install Python 3.8 or higher.
    pause
    exit /b 1
)

echo ✅ Python detected

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo ❌ Failed to create virtual environment
        pause
        exit /b 1
    )
    echo ✅ Virtual environment created
) else (
    echo ✅ Virtual environment already exists
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo ⬆️ Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo 📚 Installing required packages...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo ❌ Failed to install required packages
    pause
    exit /b 1
)

echo ✅ All packages installed successfully

REM Check if secrets.yml exists
if not exist "secrets.yml" (
    if exist "secrets.yml.template" (
        echo 📝 Creating secrets.yml from template...
        copy secrets.yml.template secrets.yml
        echo ✅ secrets.yml created from template
        echo ⚠️  Please edit secrets.yml with your AppDynamics credentials
    ) else (
        echo ⚠️  secrets.yml not found. You'll need to enter credentials manually.
    )
)

REM Run the modular version
echo 🎯 Starting AppDynamics Data Extractor (Modular Version)...
echo 🌐 The application will open in your default web browser
echo 📖 For documentation, see README_MODULAR.md and ARCHITECTURE.md
echo.
echo Press Ctrl+C to stop the application
echo.

REM Run Streamlit with the modular main.py
REM Disable telemetry and run in headless mode to avoid email prompts
set STREAMLIT_SERVER_HEADLESS=true
streamlit run main.py --server.headless true

REM Deactivate virtual environment when done
echo.
echo 🔧 Deactivating virtual environment...
call venv\Scripts\deactivate.bat

echo 👋 AppDynamics Data Extractor stopped
pause
