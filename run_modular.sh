#!/bin/bash

# AppDynamics Data Extractor - Modular Version
# This script sets up and runs the modular version of the AppDynamics Data Extractor

echo "🚀 Starting AppDynamics Data Extractor (Modular Version)"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check Python version
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python $python_version is installed, but Python $required_version or higher is required."
    exit 1
fi

echo "✅ Python $python_version detected"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment"
        exit 1
    fi
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📚 Installing required packages..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install required packages"
    exit 1
fi

echo "✅ All packages installed successfully"

# Check if secrets.yml exists
if [ ! -f "secrets.yml" ]; then
    if [ -f "secrets.yml.template" ]; then
        echo "📝 Creating secrets.yml from template..."
        cp secrets.yml.template secrets.yml
        echo "✅ secrets.yml created from template"
        echo "⚠️  Please edit secrets.yml with your AppDynamics credentials"
    else
        echo "⚠️  secrets.yml not found. You'll need to enter credentials manually."
    fi
fi

# Run the modular version
echo "🎯 Starting AppDynamics Data Extractor (Modular Version)..."
echo "🌐 The application will open in your default web browser"
echo "📖 For documentation, see README_MODULAR.md and ARCHITECTURE.md"
echo ""
echo "Press Ctrl+C to stop the application"
echo ""

# Run Streamlit with the modular main.py
# Disable telemetry and run in headless mode to avoid email prompts
STREAMLIT_SERVER_HEADLESS=true streamlit run main.py --server.headless true

# Deactivate virtual environment when done
echo ""
echo "🔧 Deactivating virtual environment..."
deactivate

echo "👋 AppDynamics Data Extractor stopped"
