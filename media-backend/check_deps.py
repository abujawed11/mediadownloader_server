#!/usr/bin/env python3
"""
Check if all dependencies are properly installed
"""
import sys
import subprocess

def check_dependency(package):
    try:
        __import__(package)
        print(f"✅ {package}")
        return True
    except ImportError:
        print(f"❌ {package} - Run: pip install {package}")
        return False

def check_system_deps():
    print("🔍 Checking system dependencies...")
    
    # Check ffmpeg
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ ffmpeg")
        else:
            print("❌ ffmpeg - Install: sudo apt-get install ffmpeg")
    except FileNotFoundError:
        print("❌ ffmpeg - Install: sudo apt-get install ffmpeg")
    
    # Check Redis
    try:
        result = subprocess.run(['redis-cli', 'ping'], 
                              capture_output=True, text=True)
        if result.returncode == 0 and 'PONG' in result.stdout:
            print("✅ redis-server (running)")
        else:
            print("⚠️  redis-server (not running) - Start: redis-server --daemonize yes")
    except FileNotFoundError:
        print("❌ redis-server - Install: sudo apt-get install redis-server")

def main():
    print("🧪 Dependency Check for Media Downloader Backend\n")
    
    print("📦 Checking Python packages...")
    required_packages = [
        'fastapi',
        'uvicorn', 
        'pydantic',
        'httpx',
        'yt_dlp',
        'redis',
        'celery',
        'loguru',
        'aiofiles',
        'orjson'
    ]
    
    all_good = True
    for package in required_packages:
        if not check_dependency(package):
            all_good = False
    
    print("\n🔧 Checking system dependencies...")
    check_system_deps()
    
    if all_good:
        print("\n✅ All Python dependencies are installed!")
        print("Run the setup test: python test_setup.py")
    else:
        print("\n❌ Some dependencies are missing.")
        print("Run: pip install -r requirements.txt")
        
if __name__ == "__main__":
    main()