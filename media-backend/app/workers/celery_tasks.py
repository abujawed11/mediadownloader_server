import os
import uuid
import time
from typing import Dict, Any, Optional
from celery import current_task

from ..core.celery_app import celery_app
from ..core.logging import get_logger
from ..services.storage_local import tmp_path, move_into_storage
from ..services.ffmpeg_simple import merge_simple_reliable
from ..services.ytdlp_service import extract_info
from ..services.redis_conn import get_redis

# Import httpx lazily to avoid import issues
try:
    import httpx
except ImportError:
    httpx = None

log = get_logger(__name__)

def update_task_progress(status: str, progress: float = None, **extra):
    """Update Celery task progress with Redis pub/sub"""
    if not current_task:
        return
        
    meta = {
        "status": status,
        "timestamp": time.time(),
        **extra
    }
    
    if progress is not None:
        meta["progress"] = max(0.0, min(1.0, progress))
    
    # Update Celery task state
    current_task.update_state(state=status.upper(), meta=meta)
    
    # Publish to Redis for real-time updates
    try:
        redis_client = get_redis()
        channel = f"tasks:{current_task.request.id}"
        import json
        redis_client.publish(channel, json.dumps({
            "task_id": current_task.request.id,
            **meta
        }))
    except Exception as e:
        log.warning(f"Failed to publish progress: {e}")

@celery_app.task(bind=True)
def stream_download(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stream download for progressive formats - faster and more reliable
    """
    url = payload["url"]
    format_id = payload["format_id"]
    title = payload.get("title", "download").strip() or "download"
    
    safe_title = "".join(c if c.isalnum() or c in " ._-" else "_" for c in title)
    uid = uuid.uuid4().hex[:8]
    
    log.info(f"[{self.request.id}] Starting stream download: {url}")
    update_task_progress("starting", 0.0, message="Extracting stream info...")
    
    # Check if httpx is available
    if httpx is None:
        raise Exception("httpx is not installed. Please run: pip install httpx")
    
    try:
        # Extract info to get direct URL
        info = extract_info(url)
        
        # Find the target format
        target_format = None
        for fmt in info.get("formats", []):
            if str(fmt.get("format_id")) == str(format_id):
                # Ensure it's progressive (has both video and audio)
                vcodec = str(fmt.get("vcodec", "none"))
                acodec = str(fmt.get("acodec", "none"))
                if vcodec != "none" and acodec != "none":
                    target_format = fmt
                    break
        
        if not target_format:
            raise Exception(f"Progressive format {format_id} not found")
        
        direct_url = target_format.get("url")
        if not direct_url:
            raise Exception("No direct URL available")
        
        # Get file info
        ext = target_format.get("ext", "mp4")
        filesize = target_format.get("filesize") or target_format.get("filesize_approx", 0)
        
        update_task_progress("downloading", 0.1, 
                           message="Starting download...", 
                           total_bytes=filesize)
        
        # Stream download with progress
        output_path = tmp_path(f"{safe_title}-{uid}.{ext}")
        
        downloaded_bytes = 0
        chunk_size = 1024 * 1024  # 1MB chunks
        start_time = time.time()
        
        with httpx.stream("GET", direct_url, timeout=60.0) as response:
            response.raise_for_status()
            
            # Get actual content length if not provided
            if not filesize:
                filesize = int(response.headers.get("content-length", 0))
                update_task_progress("downloading", 0.1, total_bytes=filesize)
            
            with open(output_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=chunk_size):
                    f.write(chunk)
                    downloaded_bytes += len(chunk)
                    
                    if filesize > 0:
                        progress = 0.1 + 0.8 * (downloaded_bytes / filesize)
                        update_task_progress("downloading", progress,
                                           downloaded_bytes=downloaded_bytes,
                                           total_bytes=filesize,
                                           speed_mbps=round(downloaded_bytes / (1024*1024) / max(1, time.time() - start_time), 2))
        
        # Move to storage
        update_task_progress("finalizing", 0.95, message="Moving to storage...")
        final_name = f"{safe_title}.{ext}"
        final_path = move_into_storage(output_path, final_name)
        final_size = os.path.getsize(final_path)
        
        mime_type = {
            "mp4": "video/mp4",
            "webm": "video/webm",
            "mkv": "video/x-matroska",
            "m4a": "audio/mp4",
            "mp3": "audio/mpeg"
        }.get(ext, "application/octet-stream")
        
        result = {
            "path": final_path,
            "file_name": final_name,
            "mime": mime_type,
            "size_bytes": final_size,
            "method": "stream"
        }
        
        update_task_progress("completed", 1.0, 
                           message="Download completed", 
                           **result)
        
        log.info(f"[{self.request.id}] Stream download completed: {final_path}")
        return result
        
    except Exception as e:
        log.error(f"[{self.request.id}] Stream download failed: {e}")
        update_task_progress("failed", message=str(e))
        raise

@celery_app.task(bind=True)
def download_and_merge(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Download and merge for formats requiring muxing - simplified and reliable
    """
    url = payload["url"]
    format_spec = payload["format"]
    title = payload.get("title", "download").strip() or "download"
    
    safe_title = "".join(c if c.isalnum() or c in " ._-" else "_" for c in title)
    uid = uuid.uuid4().hex[:8]
    
    log.info(f"[{self.request.id}] Starting merge download: {url}")
    update_task_progress("starting", 0.0, message="Extracting info...")
    
    try:
        if "+" not in format_spec:
            raise Exception("Invalid merge format specification")
        
        video_id, audio_id = format_spec.split("+", 1)
        
        # Use optimized yt-dlp download with better settings
        from ..services.ytdlp_optimized import download_format
        
        # Download video (0-40%)
        update_task_progress("downloading", 0.0, message="Downloading video...")
        video_path = download_format(url, video_id, f"{safe_title}-{uid}-video",
                                   progress_callback=lambda p: update_task_progress("downloading", p * 0.4, part="video"))
        
        # Download audio (40-80%)
        update_task_progress("downloading", 0.4, message="Downloading audio...")
        audio_path = download_format(url, audio_id, f"{safe_title}-{uid}-audio",
                                   progress_callback=lambda p: update_task_progress("downloading", 0.4 + p * 0.4, part="audio"))
        
        # Merge (80-100%)
        update_task_progress("merging", 0.8, message="Merging files...")
        
        # Determine best output format
        container = "mkv"  # Use MKV as default for reliability
        output_path = tmp_path(f"{safe_title}-{uid}-final.{container}")
        
        merge_simple_reliable(
            video_path, audio_path, output_path,
            progress_callback=lambda p: update_task_progress("merging", 0.8 + p * 0.2)
        )
        
        # Finalize
        update_task_progress("finalizing", 0.95, message="Moving to storage...")
        final_name = f"{safe_title}.{container}"
        final_path = move_into_storage(output_path, final_name)
        final_size = os.path.getsize(final_path)
        
        # Clean up temp files
        for temp_file in [video_path, audio_path]:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass
        
        mime_type = "video/x-matroska"
        
        result = {
            "path": final_path,
            "file_name": final_name,
            "mime": mime_type,
            "size_bytes": final_size,
            "method": "merge"
        }
        
        update_task_progress("completed", 1.0, 
                           message="Download and merge completed", 
                           **result)
        
        log.info(f"[{self.request.id}] Merge download completed: {final_path}")
        return result
        
    except Exception as e:
        log.error(f"[{self.request.id}] Merge download failed: {e}")
        update_task_progress("failed", message=str(e))
        raise