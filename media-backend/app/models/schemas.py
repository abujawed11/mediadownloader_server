from typing import Optional, Dict, List
from pydantic import BaseModel, Field
from .job_models import JobStatus

# ---- /media/info ----
class InfoRequest(BaseModel):
    url: str

class FormatOption(BaseModel):
    format_string: str
    label: str
    ext: Optional[str] = None
    note: Optional[str] = None
    sizeBytes: Optional[int] = None  # number | null on RN side

class InfoResponse(BaseModel):
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    formats: List[FormatOption] = Field(default_factory=list)

# ---- /media/direct-url ----
class DirectUrlRequest(BaseModel):
    url: str
    format_id: str

class DirectUrlResponse(BaseModel):
    url: str
    headers: Optional[Dict[str, str]] = None
    mime: Optional[str] = None
    fileName: Optional[str] = None

# ---- /media/jobs ----
class CreateJobRequest(BaseModel):
    url: str
    format: str     # e.g. "299+140" or "18"
    title: Optional[str] = None
    ext: Optional[str] = None      # hint for final ext (mp4/webm)

class JobResponse(BaseModel):
    id: str
    status: JobStatus
    progress01: float = 0.0
    message: Optional[str] = None
    fileName: Optional[str] = None
    mime: Optional[str] = None
    sizeBytes: Optional[int] = None
