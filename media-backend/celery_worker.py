#!/usr/bin/env python3
"""
Celery Worker Entry Point
Run with: celery -A celery_worker worker --loglevel=info --queues=downloads,streams
"""

from app.core.celery_app import celery_app

if __name__ == "__main__":
    celery_app.start()