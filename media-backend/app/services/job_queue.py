# app/services/job_queue.py
from typing import Dict, Any
from rq import Queue
from rq.job import Job
from .redis_conn import get_queue
from ..core.config import get_settings
from ..core.logging import get_logger
from ..workers.tasks.download_merge import download_and_merge   # 👈 import the callable

log = get_logger(__name__)

def enqueue_download_merge(payload: Dict[str, Any]) -> Job:
    """
    payload expects: { url, format, title?, ext? }
    """
    q: Queue = get_queue()
    s = get_settings()

    # NOTE: Avoid q.default_timeout (not present on some rq versions).
    job = q.enqueue(
        download_and_merge,
        payload,
        job_timeout=s.RQ_JOB_TTL,         # seconds
        result_ttl=s.RQ_RESULT_TTL,       # seconds
        failure_ttl=s.RQ_FAILURE_TTL,     # seconds
        meta={"progress01": 0.0, "status": "queued", "message": "queued"},
        description=f"download_and_merge {payload.get('title') or payload.get('url')}",
    )
    log.info("Enqueued job %s for %s", job.id, payload.get("url"))
    return job
