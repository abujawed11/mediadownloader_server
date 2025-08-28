#!/bin/bash
echo "Starting Media Downloader Backend (Development Mode)"
echo

echo "Installing/Updating dependencies..."
pip install -r requirements.txt
echo

echo "Starting Redis server (make sure Redis is running)"
echo "If Redis is not installed:"
echo "  - Ubuntu/Debian: sudo apt-get install redis-server"
echo "  - macOS: brew install redis"
echo "  - Or use Docker: docker run -d -p 6379:6379 redis:alpine"
echo

echo "Starting Celery Worker in background..."
celery -A celery_worker worker --loglevel=info --queues=downloads,streams --detach

echo "Waiting 5 seconds for worker to start..."
sleep 5

echo "Starting FastAPI Server..."
python start_server.py