# app/workers/tasks/download_merge.py

import os, uuid, time
from typing import Dict, Any, Optional
from rq import get_current_job
import yt_dlp

from ...core.logging import get_logger
from ...services.storage_local import tmp_path, move_into_storage
from ...services.ffmpeg_service import merge_with_progress_copy, ffprobe_basic
from ...services.redis_conn import get_redis  # if you use pubsub in _publish

log = get_logger(__name__)


def _guess_mime_from_ext(ext: str) -> str:
    ext = (ext or "").lower()
    return {
        "mp4": "video/mp4",
        "m4v": "video/mp4",
        "webm": "video/webm",
        "mkv": "video/x-matroska",
        "m4a": "audio/mp4",
        "mp3": "audio/mpeg",
        "opus": "audio/ogg",
    }.get(ext, "application/octet-stream")


def _set_meta(*, status: Optional[str] = None, progress01: Optional[float] = None,
              message: Optional[str] = None, **extras):
    job = get_current_job()
    if not job:
        return
    m = job.meta or {}
    if status is not None:      m["status"] = status
    if progress01 is not None:  m["progress01"] = float(max(0.0, min(1.0, progress01)))
    if message is not None:     m["message"] = message
    for k, v in extras.items(): m[k] = v
    m["finished"] = (m.get("status") == "finished")
    m["failed"]   = (m.get("status") == "failed")
    job.meta = m
    job.save_meta()
    # If you wired Redis pubsub to WS, publish here as well.


def _ydl_download(url: str, fmt: str, outpath_noext: str, part: str, base: float, span: float) -> str:
    def progress_hook(d):
        if d.get("status") == "downloading":
            try:
                downloaded = int(d.get("downloaded_bytes") or 0)
                total      = int(d.get("total_bytes") or d.get("total_bytes_estimate") or 0)
                speed      = float(d.get("speed") or 0.0)
                eta        = int(d.get("eta") or 0)
                p_local    = (downloaded / total) if total > 0 else 0.0
                p01        = base + span * max(0.0, min(1.0, p_local))  # monotonic global progress
                _set_meta(
                    status="downloading",
                    progress01=p01,
                    part=part,
                    downloadedBytes=downloaded,
                    totalBytes=(total or None),
                    speedBps=(speed or None),
                    etaSeconds=(eta or None),
                )
            except Exception:
                pass

    ydl_opts = {
        "quiet": True, "no_warnings": True,
        "outtmpl": outpath_noext + ".%(ext)s",
        "format": fmt, "progress_hooks": [progress_hook],
        "noplaylist": True,
        
        # Timeout and retry configurations
        "retries": 5,
        "fragment_retries": 5,
        "extractor_retries": 3,
        "file_access_retries": 3,
        
        # Socket timeout configurations
        "socket_timeout": 60,
        
        # HTTP configurations for better reliability
        "http_chunk_size": 10485760,  # 10MB chunks
        "concurrent_fragment_downloads": 1,  # Conservative for stability
        
        # Additional reliability options
        "continue_dl": True,  # Resume partial downloads
        "no_check_certificates": False,  # Keep certificate validation
        "prefer_insecure": False,  # Use HTTPS when available
        
        # User agent to avoid blocking
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        
        # Additional headers for better compatibility
        "headers": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-us,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
    }
    # Implement exponential backoff retry logic
    max_retries = 3
    base_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check if this is a timeout or network-related error
            if any(keyword in error_msg for keyword in [
                'timeout', 'timed out', 'connection', 'network', 
                'temporary failure', 'read operation', 'socket'
            ]):
                if attempt < max_retries - 1:  # Not the last attempt
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    log.warning(f"Network error on attempt {attempt + 1}/{max_retries}: {e}. Retrying in {delay}s...")
                    _set_meta(
                        status="retrying", 
                        message=f"Network error, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})",
                        retryAttempt=attempt + 1,
                        maxRetries=max_retries
                    )
                    time.sleep(delay)
                    continue
                else:
                    log.error(f"All retry attempts failed. Final error: {e}")
                    raise
            else:
                # Non-network error, don't retry
                log.error(f"Non-recoverable error: {e}")
                raise


def download_and_merge(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload: { url, format, title?, ext? }
    - If "format" contains "+": download video+audio separately and mux (copy).
      * If video is AV1 => mux straight to MKV (skip MP4).
    - Else: progressive direct download, then move to storage.
    Returns: { path, file_name, mime, size_bytes }
    """
    url: str = payload["url"]
    fmt: str = payload["format"]              # e.g. "299+140" or "18"
    title: str = (payload.get("title") or "download").strip() or "download"
    hint_ext: Optional[str] = payload.get("ext")

    safe_title = "".join(c if c.isalnum() or c in " ._-" else "_" for c in title)
    uid = uuid.uuid4().hex[:8]

    job = get_current_job()
    jid = job.id if job else "unknown"
    log.info("[job %s] enqueue payload url=%s fmt=%s title=%s", jid, url, fmt, title)

    try:
        _set_meta(status="started", progress01=0.0, message="started")

        # -------------------- MERGE PATH (video+audio) --------------------
        if "+" in fmt:
            v_id, a_id = fmt.split("+", 1)
            v_tmp_base = tmp_path(f"{safe_title}-{uid}-v")
            a_tmp_base = tmp_path(f"{safe_title}-{uid}-a")

            # video contributes 0..80%, audio 80..90%
            v_path = _ydl_download(url, v_id, v_tmp_base, part="video", base=0.00, span=0.80)
            a_path = _ydl_download(url, a_id, a_tmp_base, part="audio", base=0.80, span=0.10)

            # Probe the video to decide the safest target container
            vprobe = ffprobe_basic(v_path)
            vcodec = (vprobe.get("vcodec") or "").lower()
            vcontainer = (vprobe.get("container") or "").lower()

            # ✅ Force MKV for AV1 or WEBM-like sources to avoid MP4 copy stalls
            if vcodec in {"av1"} or vcontainer in {"webm", "matroska"}:
                target_container = "mkv"
            else:
                target_container = "mp4"

            log.info("[job %s] merging container=%s vcodec=%s vcontainer=%s",
                     jid, target_container, vcodec, vcontainer)

            _set_meta(status="merging", message="merging", part="merging",
                      debugContainer=target_container, debugVCodec=vcodec, debugVContainer=vcontainer)

            base_out   = tmp_path(f"{safe_title}-{uid}-merged")
            out_tmp    = f"{base_out}.{target_container}"
            ffmpeg_log = tmp_path(f"{safe_title}-{uid}-ffmpeg.log")
            log.info("[job %s] ffmpeg log -> %s", jid, ffmpeg_log)

            def on_merge_progress(p01: float, time_sec: float | None):
                _set_meta(status="merging",
                          progress01=max(0.01, min(0.99, p01)),
                          part="merging",
                          mergeTimeSec=(time_sec or None))

            def on_debug(line: str):
                # keep a rolling line in meta; mirror interesting ones to server logs
                if ("time=" in line) or ("Stream mapping" in line) or ("muxing" in line):
                    log.info("[job %s] %s", jid, line.strip())

            # One call: merge_with_progress_copy will watchdog & (if we had asked for mp4 and it failed) retry mkv
            merge_with_progress_copy(
                v_path, a_path, out_tmp,
                container=target_container,        # already "mkv" for AV1
                on_progress=on_merge_progress,
                on_debug=on_debug,
                stderr_log_path=ffmpeg_log,
            )

            # Figure out what actually got written
            produced_path = out_tmp
            produced_ext  = target_container
            if not os.path.exists(produced_path):
                alt = f"{base_out}.mkv"
                if os.path.exists(alt):
                    produced_path = alt
                    produced_ext  = "mkv"
                    log.info("[job %s] using mkv fallback %s", jid, alt)

            final_name  = f"{safe_title}.{produced_ext}"
            final_path  = move_into_storage(produced_path, final_name)
            size_bytes  = os.path.getsize(final_path)
            mime        = _guess_mime_from_ext(produced_ext)

            log.info("[job %s] merged -> %s (%d bytes, %s)", jid, final_path, size_bytes, mime)
            _set_meta(status="finished", progress01=1.0, message="done", totalBytes=size_bytes)

            return {
                "path": final_path,
                "file_name": final_name,
                "mime": mime,
                "size_bytes": size_bytes,
            }

        # -------------------- PROGRESSIVE PATH --------------------
        base      = tmp_path(f"{safe_title}-{uid}")
        file_path = _ydl_download(url, fmt, base, part="progressive", base=0.00, span=0.90)
        ext       = (os.path.splitext(file_path)[1] or "").lstrip(".") or (hint_ext or "mp4")
        final_name = f"{safe_title}.{ext}"
        final_path = move_into_storage(file_path, final_name)
        size_bytes = os.path.getsize(final_path)
        mime       = _guess_mime_from_ext(ext)

        log.info("[job %s] progressive -> %s (%d bytes, %s)", jid, final_path, size_bytes, mime)
        _set_meta(status="finished", progress01=1.0, message="done",
                  totalBytes=size_bytes, part="progressive")

        return {
            "path": final_path,
            "file_name": final_name,
            "mime": mime,
            "size_bytes": size_bytes,
        }

    except Exception as e:
        log.exception("[job %s] download_and_merge failed: %s", jid, e)
        _set_meta(status="failed", message=str(e))
        raise
