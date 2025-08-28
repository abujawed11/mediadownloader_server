#!/usr/bin/env python3
"""
Test script to verify the new setup works
"""
import os
import sys

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    print("Testing imports...")
    
    try:
        from app.core.config import get_settings
        settings = get_settings()
        print(f"✅ Config loaded - Redis URL: {settings.REDIS_URL}")
    except Exception as e:
        print(f"❌ Config failed: {e}")
        return False
    
    try:
        from app.services.redis_conn import get_redis
        redis_client = get_redis()
        redis_client.ping()
        print("✅ Redis connection successful")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("   Make sure Redis is running: redis-server or docker run -d -p 6379:6379 redis:alpine")
        return False
    
    try:
        from app.core.celery_app import celery_app
        print(f"✅ Celery app created - Broker: {celery_app.conf.broker_url}")
    except Exception as e:
        print(f"❌ Celery app failed: {e}")
        return False
    
    try:
        from app.workers.celery_tasks import stream_download, download_and_merge
        print("✅ Celery tasks imported successfully")
    except Exception as e:
        print(f"❌ Celery tasks failed: {e}")
        return False
    
    try:
        from app.main import app
        print("✅ FastAPI app imported successfully")
    except Exception as e:
        print(f"❌ FastAPI app failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🧪 Testing Media Downloader Setup\n")
    
    if test_imports():
        print("\n🎉 All tests passed! You can now start the server:")
        print("   python start_server.py")
        print("   celery -A celery_worker worker --loglevel=info --queues=downloads,streams")
    else:
        print("\n❌ Some tests failed. Check the errors above.")
        sys.exit(1)