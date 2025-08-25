from typing import Optional, Dict, Any
from rq import Queue
from rq.job import Job
from .redis_conn import get_queue
from ..core.logging import get_logger

log = get_logger(__name__)

def enqueue_download_merge(payload: Dict[str, Any]) -> Job:
    """
    payload expects: { url, format, title?, ext? }
    """
    q: Queue = get_queue()
    job = q.enqueue(
        "app.workers.tasks.download_merge.download_and_merge",
        payload,
        job_timeout=q.default_timeout,
        meta={"progress01": 0.0, "status": "queued", "message": "queued"},
        description=f"download_and_merge {payload.get('title') or payload.get('url')}"
    )
    log.info("Enqueued job %s for %s", job.id, payload.get("url"))
    return job
