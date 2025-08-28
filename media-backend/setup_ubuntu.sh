#!/bin/bash
echo "🔧 Setting up Media Downloader Backend on Ubuntu/WSL2"
echo

echo "📦 Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y redis-server ffmpeg python3-pip

echo "🔧 Starting Redis service..."
sudo systemctl start redis-server
sudo systemctl enable redis-server

echo "🐍 Installing Python dependencies..."
pip install -r requirements.txt

echo "🧪 Testing setup..."
python test_setup.py

echo
echo "✅ Setup complete! You can now run:"
echo "   ./start_development.sh"
echo
echo "Or manually:"
echo "   python start_server.py              # In one terminal"
echo "   celery -A celery_worker worker --loglevel=info --queues=downloads,streams  # In another terminal"