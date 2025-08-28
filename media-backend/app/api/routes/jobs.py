from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from typing import List, Dict, Any
from ...models.schemas import CreateJobRequest, JobResponse
from ...models.job_models import JobStatus
from ...services.job_queue import enqueue_download_merge, enqueue_stream_download, get_task_status
from ...core.logging import get_logger
import os

router = APIRouter(prefix="/media", tags=["jobs"])
log = get_logger(__name__)



# @router.get("/jobs/{job_id}/progress")
# def job_progress(job_id: str):
#     q = get_queue()
#     job = q.fetch_job(job_id)
#     if not job:
#         raise HTTPException(status_code=404, detail="Job not found")
#     m = job.meta or {}
#     # Minimal payload for cheap polling
#     return {
#         "id": job.get_id(),
#         "status": m.get("status", "queued"),
#         "progress01": float(m.get("progress01", 0.0)),
#         "message": m.get("message"),
#         "finished": bool(job.is_finished),
#         "failed": bool(job.is_failed),
#     }


# def _job_to_response(job: Job) -> JobResponse:
#     meta = job.meta or {}
#     return JobResponse(
#         id=job.get_id(),
#         status=JobStatus(meta.get("status", "queued")),
#         progress01=float(meta.get("progress01", 0.0)),
#         message=meta.get("message"),
#         fileName=(job.result or {}).get("file_name") if job.is_finished else None,
#         mime=(job.result or {}).get("mime") if job.is_finished else None,
#         sizeBytes=(job.result or {}).get("size_bytes") if job.is_finished else None,
#     )

def task_progress(task_id: str) -> Dict[str, Any]:
    """Get progress for a Celery task"""
    return get_task_status(task_id)

def _task_to_response(task_status: Dict[str, Any]) -> JobResponse:
    """Convert task status to JobResponse"""
    status_map = {
        "success": "done", 
        "failure": "error", 
        "pending": "queued",
        "started": "running",
        "completed": "done",
        "failed": "error"
    }
    
    raw_status = task_status.get("status", "pending")
    mapped_status = status_map.get(raw_status, raw_status)
    
    return JobResponse(
        id=task_status.get("id"),
        status=JobStatus(mapped_status),
        progress01=float(task_status.get("progress", 0.0)),
        message=task_status.get("message"),
        fileName=task_status.get("file_name") if task_status.get("ready") else None,
        mime=task_status.get("mime") if task_status.get("ready") else None,
        sizeBytes=task_status.get("size_bytes") if task_status.get("ready") else None,
    )



@router.post("/tasks", response_model=JobResponse)
def create_task(body: CreateJobRequest) -> JobResponse:
    """
    Create a download task - automatically chooses best method
    """
    format_spec = body.format
    payload = body.model_dump()
    
    if "+" in format_spec:
        # Merge required
        task = enqueue_download_merge(payload)
    else:
        # Progressive download
        task = enqueue_stream_download(payload)
    
    return _task_to_response({"id": task.id, "status": "pending", "progress": 0.0})

@router.get("/tasks/{task_id}", response_model=JobResponse)
def get_task(task_id: str) -> JobResponse:
    """Get task status"""
    task_status = get_task_status(task_id)
    return _task_to_response(task_status)

@router.get("/tasks/{task_id}/file")
def get_task_file(task_id: str):
    """
    Serve the final file for a completed task
    """
    task_status = get_task_status(task_id)
    
    if task_status.get("status") not in ["success", "completed"]:
        raise HTTPException(status_code=409, detail="Task not completed")
    
    file_path = task_status.get("path")
    file_name = task_status.get("file_name")
    mime = task_status.get("mime", "application/octet-stream")
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path, 
        filename=file_name, 
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "X-Android-Download-Manager": "true"
        }
    )

# Legacy endpoints for backward compatibility
@router.post("/jobs", response_model=JobResponse) 
def create_job_legacy(body: CreateJobRequest) -> JobResponse:
    """Legacy endpoint - redirects to new task system"""
    return create_task(body)

@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_legacy(job_id: str) -> JobResponse:
    """Legacy endpoint"""
    return get_task(job_id)

@router.get("/jobs/{job_id}/file")
def get_job_file_legacy(job_id: str):
    """Legacy endpoint"""
    return get_task_file(job_id)




# app/api/routes/jobs.py  (only show changed parts)


