#!/usr/bin/env python3
"""
Celery Worker Entry Point
Run with: celery -A celery_worker worker --loglevel=info --queues=downloads,streams
"""
import os
import sys

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.celery_app import celery_app

if __name__ == "__main__":
    celery_app.start()