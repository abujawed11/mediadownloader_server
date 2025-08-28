@echo off
echo Starting Media Downloader Backend (Development Mode)
echo.

echo Installing/Updating dependencies...
pip install -r requirements.txt
echo.

echo Starting Redis server (make sure Redis is running)
echo If Redis is not installed, install it first:
echo   - Windows: Download from https://redis.io/download
echo   - Or use Docker: docker run -d -p 6379:6379 redis:alpine
echo.

echo Starting Celery Worker...
start "Celery Worker" cmd /k "celery -A celery_worker worker --loglevel=info --queues=downloads,streams --pool=solo"

echo Waiting 5 seconds for worker to start...
timeout /t 5 /nobreak >nul

echo Starting FastAPI Server...
python start_server.py

pause