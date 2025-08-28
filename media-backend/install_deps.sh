#!/bin/bash
echo "🔧 Installing all dependencies for Media Downloader Backend"
echo

echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🧪 Checking installation..."
python check_deps.py

echo
echo "If all checks pass, you can now run:"
echo "  python test_setup.py     # Test the setup"
echo "  ./start_development.sh   # Start the server"
echo

# Make sure scripts are executable
chmod +x start_development.sh
chmod +x setup_ubuntu.sh