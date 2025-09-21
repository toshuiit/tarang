#!/bin/bash

# Local Development Setup for Tarang Web Application
# Run this script to set up and start the application locally

set -e

echo "🚀 Setting up Tarang Web Application locally..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8+ first."
    exit 1
fi

# Install python3-venv if not available (Ubuntu 24.04 requirement)
if ! python3 -m venv --help &> /dev/null; then
    echo "📦 Installing python3-venv..."
    sudo apt update
    sudo apt install -y python3-venv python3-full
fi

# Remove existing venv if it exists (to fix any corruption)
if [ -d "venv" ]; then
    echo "🗑️ Removing existing virtual environment..."
    rm -rf venv
fi

# Create fresh virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Verify we're in the virtual environment
echo "📍 Virtual environment path: $(which python)"

# Upgrade pip in virtual environment (should work now)
echo "⬆️ Upgrading pip..."
./venv/bin/pip install --upgrade pip

# Install dependencies using venv pip directly
echo "📥 Installing Python dependencies..."
./venv/bin/pip install -r web_requirements.txt

# Check if all required packages are installed
echo "✅ Checking dependencies..."
python3 -c "
import flask
import flask_socketio
import flask_login
print('✅ All dependencies installed successfully!')
"

echo ""
echo "🌐 Starting Tarang Web Application..."
echo "📍 Application will be available at: http://localhost:5000"
echo "🔄 Press Ctrl+C to stop the server"
echo ""

# Start the Flask application
python3 app.py
