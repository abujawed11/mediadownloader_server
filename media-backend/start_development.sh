#!/bin/bash
echo "🚀 Starting Media Downloader Backend (Development Mode)"
echo

echo "📦 Installing/Updating dependencies..."
pip install -r requirements.txt
echo

echo "🧪 Testing setup..."
python test_setup.py
if [ $? -ne 0 ]; then
    echo "❌ Setup test failed. Please fix the errors above."
    exit 1
fi
echo

echo "🔧 Checking Redis server..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Redis is not running. Starting Redis..."
    if command -v redis-server > /dev/null; then
        redis-server --daemonize yes --port 6379
        sleep 2
    elif command -v docker > /dev/null; then
        echo "Starting Redis with Docker..."
        docker run -d --name media-redis -p 6379:6379 redis:alpine
        sleep 3
    else
        echo "❌ Redis not found. Please install Redis:"
        echo "  - Ubuntu/Debian: sudo apt-get install redis-server"
        echo "  - macOS: brew install redis"
        echo "  - Or use Docker: docker run -d -p 6379:6379 redis:alpine"
        exit 1
    fi
fi

echo "✅ Redis is running"
echo

echo "🔄 Starting Celery Worker in background..."
celery -A celery_worker worker --loglevel=info --queues=downloads,streams --detach

echo "⏳ Waiting 3 seconds for worker to start..."
sleep 3

echo "🌐 Starting FastAPI Server..."
echo "Server will be available at: http://localhost:8000"
echo "API docs will be at: http://localhost:8000/docs"
echo
python start_server.py