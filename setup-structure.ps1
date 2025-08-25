# setup-structure.ps1
# Creates: media-backend/ (FastAPI + RQ + yt-dlp + FFmpeg + Redis skeleton)

$ErrorActionPreference = "Stop"

$root = "media-backend"

$dirs = @(
  "$root/app",
  "$root/app/api/routes",
  "$root/app/core",
  "$root/app/models",
  "$root/app/services",
  "$root/app/workers/tasks",
  "$root/app/utils",
  "$root/tests"
)

# Create directories
foreach ($d in $dirs) {
  if (-not (Test-Path $d)) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
  }
}

# ---------- File contents (single-quoted here-strings -> no variable expansion) ----------

$files = @{}

$files["$root/.env.example"] = @'
APP_ENV=dev
APP_HOST=0.0.0.0
APP_PORT=8000
REDIS_URL=redis://localhost:6379/0

# local disk paths for dev
WORK_DIR=/tmp/media-work
OUTPUT_DIR=/tmp/media-out

# yt-dlp tuning
YTDLP_PLAYER_CLIENT=web

# CORS (add your Expo dev URL or LAN IP)
CORS_ORIGINS=http://localhost:8081,http://127.0.0.1:8081
'@

$files["$root/requirements.txt"] = @'
fastapi
uvicorn[standard]
pydantic-settings
python-multipart
httpx
tenacity
yt-dlp
redis
rq
rq-scheduler
boto3
loguru
python-slugify
orjson
'@

$files["$root/README.md"] = @'
# Media Backend (FastAPI + RQ + yt-dlp + FFmpeg + Redis)

## Dev quickstart (Linux/WSL2)
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip ffmpeg redis-server
python3.11 -m venv .venv && source .venv/bin/activate
pip install -U pip wheel && pip install -r requirements.txt
# terminal A:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# terminal B:
python -m app.workers.worker
'@

$files["$root/app/__init__.py"] = @'
'@

$files["$root/app/main.py"] = @'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import media, jobs

app = FastAPI(title="Media Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(media.router, prefix="/media", tags=["media"])
app.include_router(jobs.router, prefix="/media", tags=["jobs"])

@app.get("/health")
def health():
    return {"ok": True}
'@

$files["$root/app/api/routes/__init__.py"] = @'
'@

$files["$root/app/api/routes/media.py"] = @'
from fastapi import APIRouter

router = APIRouter()

@router.get("/info")
def info():
    # TODO: wire to yt-dlp extract_info
    return {"msg": "info endpoint placeholder"}

@router.post("/direct-url")
def direct_url():
    # TODO: return progressive URL + http_headers for RNBD
    return {"msg": "direct-url placeholder"}
'@

$files["$root/app/api/routes/jobs.py"] = @'
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
'@

$files["$root/app/core/__init__.py"] = @'
'@

$files["$root/app/core/config.py"] = @'
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    APP_ENV: str = "dev"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    REDIS_URL: str = "redis://localhost:6379/0"

    WORK_DIR: str = "/tmp/media-work"
    OUTPUT_DIR: str = "/tmp/media-out"

    YTDLP_PLAYER_CLIENT: str = "web"
    CORS_ORIGINS: List[str] = ["http://localhost:8081"]

    class Config:
        env_file = ".env"

settings = Settings()
'@

$files["$root/app/core/logging.py"] = @'
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("media-backend")
'@

$files["$root/app/models/__init__.py"] = @'
'@

$files["$root/app/models/schemas.py"] = @'
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

class InfoRequest(BaseModel):
    url: str

class FormatItem(BaseModel):
    itag: str
    ext: str
    height: Optional[int] = None
    fps: Optional[int] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    container: Optional[str] = None
    sizeBytes: Optional[int] = None
    isProgressive: bool = False
    isMerge: bool = False
    display: str

class InfoResponse(BaseModel):
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    formats: List[Dict[str, Any]]
'@

$files["$root/app/models/job_models.py"] = @'
from enum import Enum

class JobStatus(str, Enum):
    queued = "queued"
    downloading = "downloading"
    merging = "merging"
    done = "done"
    error = "error"
    paused = "paused"
    canceled = "canceled"
'@

$files["$root/app/services/__init__.py"] = @'
'@

$files["$root/app/services/redis_conn.py"] = @'
import redis
from app.core.config import settings

def get_redis():
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=False)
'@

$files["$root/app/services/job_queue.py"] = @'
from rq import Queue
from app.services.redis_conn import get_redis

_q = None

def default_queue() -> Queue:
    global _q
    if _q is None:
        _q = Queue("default", connection=get_redis())
    return _q

def enqueue_extract(url: str):
    from app.workers.tasks.extract import extract_info_task
    return default_queue().enqueue(extract_info_task, url)

def enqueue_merge(url: str, fmt_selector: str, title_hint: str = ""):
    from app.workers.tasks.download_merge import download_merge_task
    return default_queue().enqueue(download_merge_task, url, fmt_selector, title_hint)
'@

$files["$root/app/services/ytdlp_service.py"] = @'
# placeholder for yt-dlp logic
# implement: extract_info(url), build_formats(data), normalize pairs, etc.
'@

$files["$root/app/services/ffmpeg_service.py"] = @'
# placeholder for ffmpeg helpers
# implement: merge_to_mp4(video_path, audio_path, out_path) using -c copy
'@

$files["$root/app/services/storage_local.py"] = @'
# save files locally to OUTPUT_DIR
# implement: save_temp, promote, build_file_response
'@

$files["$root/app/services/storage_s3.py"] = @'
# save files to S3/CDN (later)
# implement with boto3: put_object, presign url, etc.
'@

$files["$root/app/workers/__init__.py"] = @'
'@

$files["$root/app/workers/worker.py"] = @'
from rq import Worker, Queue, Connection
from app.services.redis_conn import get_redis

if __name__ == "__main__":
    with Connection(get_redis()):
        Worker([Queue("default")]).work()
'@

$files["$root/app/workers/tasks/__init__.py"] = @'
'@

$files["$root/app/workers/tasks/extract.py"] = @'
# placeholder for extract task
# def extract_info_task(url: str): ...
'@

$files["$root/app/workers/tasks/download_merge.py"] = @'
# placeholder for download + merge task
# def download_merge_task(url: str, fmt_selector: str, title_hint: str = ""): ...
'@

$files["$root/app/utils/__init__.py"] = @'
'@

$files["$root/app/utils/bytes_fmt.py"] = @'
def fmt_bytes(n: int) -> str:
    if n is None:
        return "—"
    units = ["B","KB","MB","GB","TB"]
    u = 0
    v = float(n)
    while v >= 1024 and u < len(units) - 1:
        v /= 1024
        u += 1
    return f"{v:.1f} {units[u]}"
'@

$files["$root/app/utils/timers.py"] = @'
# timing helpers (e.g., simple stopwatch)
import time

class Timer:
    def __enter__(self):
        self.t0 = time.time()
        return self
    def __exit__(self, *exc):
        self.dt = time.time() - self.t0
'@

$files["$root/tests/test_smoke.py"] = @'
def test_smoke():
    assert 1 + 1 == 2
'@

# ---------- Write files ----------
foreach ($path in $files.Keys) {
  $content = $files[$path]
  if (-not (Test-Path $path)) {
    New-Item -ItemType File -Force -Path $path | Out-Null
  }
  # Write as UTF-8 without BOM
  $content | Out-File -FilePath $path -Encoding utf8 -Force
}

Write-Host "✅ Folder structure created under $root"
