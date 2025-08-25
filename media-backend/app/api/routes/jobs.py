from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from typing import List
from rq.job import Job
from ...models.schemas import CreateJobRequest, JobResponse
from ...models.job_models import JobStatus
from ...services.job_queue import enqueue_download_merge
from ...services.redis_conn import get_queue
from ...core.logging import get_logger

router = APIRouter(prefix="/media", tags=["jobs"])
log = get_logger(__name__)


def _job_to_response(job: Job) -> JobResponse:
    meta = job.meta or {}
    return JobResponse(
        id=job.get_id(),
        status=JobStatus(meta.get("status", "queued")),
        progress01=float(meta.get("progress01", 0.0)),
        message=meta.get("message"),
        fileName=(job.result or {}).get("file_name") if job.is_finished else None,
        mime=(job.result or {}).get("mime") if job.is_finished else None,
        sizeBytes=(job.result or {}).get("size_bytes") if job.is_finished else None,
    )


@router.post("/jobs", response_model=JobResponse)
def create_job(body: CreateJobRequest) -> JobResponse:
    """
    Enqueue a download/merge job.
    """
    job = enqueue_download_merge(body.model_dump())
    return _job_to_response(job)


@router.get("/jobs", response_model=List[JobResponse])
def list_jobs() -> List[JobResponse]:
    """
    List recent jobs in the queue (best-effort).
    """
    q = get_queue()
    jobs = []
    # Inspect both finished & started/queued (best-effort, not paginated)
    for j in q.jobs:
        jobs.append(_job_to_response(j))
    for j in q.finished_job_registry.get_job_ids()[:50]:
        job = q.fetch_job(j)
        if job:
            jobs.append(_job_to_response(job))
    for j in q.failed_job_registry.get_job_ids()[:50]:
        job = q.fetch_job(j)
        if job:
            jobs.append(_job_to_response(job))
    return jobs


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    q = get_queue()
    job = q.fetch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)


@router.get("/jobs/{job_id}/file")
def get_job_file(job_id: str):
    """
    Serve the final file for a finished job from local storage.
    """
    q = get_queue()
    job = q.fetch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.is_finished or not isinstance(job.result, dict):
        raise HTTPException(status_code=409, detail="Job is not finished")
    path = job.result.get("path")
    file_name = job.result.get("file_name")
    if not path or not file_name:
        raise HTTPException(status_code=404, detail="File not available")
    return FileResponse(path, filename=file_name, media_type=job.result.get("mime") or "application/octet-stream")
