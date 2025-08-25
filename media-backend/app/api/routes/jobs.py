from fastapi import APIRouter

router = APIRouter()

@router.get("/jobs")
def list_jobs():
    # TODO: list queued/running/done jobs
    return {"items": []}

@router.post("/jobs")
def create_job():
    # TODO: enqueue merge task
    return {"id": "job_123"}

@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    # TODO: return job status
    return {"id": job_id, "status": "queued"}

@router.get("/jobs/{job_id}/file")
def get_job_file(job_id: str):
    # TODO: stream or 302 to file
    return {"id": job_id, "url": "/files/example.mp4"}
