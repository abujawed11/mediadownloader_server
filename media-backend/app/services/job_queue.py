# app/services/job_queue.py
from typing import Dict, Any, Optional
from celery.result import AsyncResult
from ..core.celery_app import celery_app
from ..core.logging import get_logger

log = get_logger(__name__)

def enqueue_download_merge(payload: Dict[str, Any]) -> AsyncResult:
    """
    payload expects: { url, format, title?, ext? }
    """
    from ..workers.celery_tasks import download_and_merge
    
    task = download_and_merge.delay(payload)
    log.info("Enqueued Celery task %s for %s", task.id, payload.get("url"))
    return task

def enqueue_stream_download(payload: Dict[str, Any]) -> AsyncResult:
    """
    For progressive formats that can be streamed directly
    payload expects: { url, format_id, title?, ext? }
    """
    from ..workers.celery_tasks import stream_download
    
    task = stream_download.delay(payload)
    log.info("Enqueued stream task %s for %s", task.id, payload.get("url"))
    return task

def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get task status and metadata"""
    task = AsyncResult(task_id, app=celery_app)
    
    result = {
        "id": task_id,
        "status": task.status.lower(),
        "ready": task.ready(),
    }
    
    if hasattr(task, 'info') and task.info:
        if isinstance(task.info, dict):
            result.update(task.info)
        elif task.status == "FAILURE":
            result["error"] = str(task.info)
    
    return result
