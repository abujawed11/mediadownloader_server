# # placeholder for download + merge task
# # def download_merge_task(url: str, fmt_selector: str, title_hint: str = ""): ...
# import os
# import yt_dlp
# import uuid
# from typing import Dict, Any, Optional, Tuple
# from rq import get_current_job

# from ...core.logging import get_logger
# from ...services.storage_local import tmp_path, move_into_storage
# from ...services.ffmpeg_service import merge_to_mp4

# log = get_logger(__name__)


# def _set_meta(status: str = None, progress: float = None, message: str = None):
#     job = get_current_job()
#     if not job:
#         return
#     if status is not None:
#         job.meta["status"] = status
#     if progress is not None:
#         job.meta["progress01"] = float(progress)
#     if message is not None:
#         job.meta["message"] = message
#     job.save_meta()


# def _ydl_download(url: str, fmt: str, outpath: str) -> str:
#     """
#     Download a single format to the given path (without extension).
#     Returns the final absolute file path including extension.
#     """
#     def progress_hook(d):
#         if d.get("status") == "downloading":
#             # best-effort normalized progress
#             try:
#                 p = float(d.get("downloaded_bytes", 0)) / float(d.get("total_bytes", d.get("total_bytes_estimate", 1)))
#                 _set_meta(status="downloading", progress=max(0.01, min(0.99, p)))
#             except Exception:
#                 pass

#     ydl_opts = {
#         "quiet": True,
#         "no_warnings": True,
#         "outtmpl": outpath + ".%(ext)s",
#         "format": fmt,
#         "progress_hooks": [progress_hook],
#         "noplaylist": True,
#     }
#     with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#         res = ydl.extract_info(url, download=True)
#         return ydl.prepare_filename(res)  # actual file path


# def _guess_mime_from_ext(ext: str) -> str:
#     ext = (ext or "").lower()
#     return {
#         "mp4": "video/mp4",
#         "m4v": "video/mp4",
#         "webm": "video/webm",
#         "mkv": "video/x-matroska",
#         "m4a": "audio/mp4",
#         "mp3": "audio/mpeg",
#         "opus": "audio/ogg",
#     }.get(ext, "application/octet-stream")


# def download_and_merge(payload: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     payload: { url, format, title?, ext? }
#     - If format contains "+": download parts separately and mux with ffmpeg -c copy to mp4.
#     - Else: progressive; download directly and move into storage.
#     Returns: { path, file_name, mime, size_bytes }
#     """
#     url: str = payload["url"]
#     fmt: str = payload["format"]              # e.g. "299+140" or "18"
#     title: str = (payload.get("title") or "download").strip() or "download"
#     hint_ext: Optional[str] = payload.get("ext")

#     safe_title = "".join(c if c.isalnum() or c in " ._-" else "_" for c in title)
#     uid = uuid.uuid4().hex[:8]

#     try:
#         _set_meta(status="started", progress=0.0, message="started")

#         if "+" in fmt:
#             # Download video & audio separately
#             v_id, a_id = fmt.split("+", 1)
#             v_tmp_base = tmp_path(f"{safe_title}-{uid}-v")
#             a_tmp_base = tmp_path(f"{safe_title}-{uid}-a")
#             v_path = _ydl_download(url, v_id, v_tmp_base)
#             a_path = _ydl_download(url, a_id, a_tmp_base)

#             _set_meta(status="merging", message="merging")

#             # Final container = mp4 (works for most sites when codecs are H.264/AAC)
#             final_name = f"{safe_title}.mp4"
#             out_tmp = tmp_path(f"{safe_title}-{uid}-merged.mp4")
#             merge_to_mp4(v_path, a_path, out_tmp)

#             # Move to storage
#             final_path = move_into_storage(out_tmp, final_name)
#             size_bytes = os.path.getsize(final_path)
#             mime = _guess_mime_from_ext("mp4")

#             _set_meta(status="finished", progress=1.0, message="done")

#             return {
#                 "path": final_path,
#                 "file_name": final_name,
#                 "mime": mime,
#                 "size_bytes": size_bytes,
#             }

#         # Progressive single download
#         base = tmp_path(f"{safe_title}-{uid}")
#         file_path = _ydl_download(url, fmt, base)
#         ext = (os.path.splitext(file_path)[1] or "").lstrip(".") or (hint_ext or "mp4")
#         final_name = f"{safe_title}.{ext}"
#         final_path = move_into_storage(file_path, final_name)
#         size_bytes = os.path.getsize(final_path)
#         mime = _guess_mime_from_ext(ext)

#         _set_meta(status="finished", progress=1.0, message="done")

#         return {
#             "path": final_path,
#             "file_name": final_name,
#             "mime": mime,
#             "size_bytes": size_bytes,
#         }

#     except Exception as e:
#         log.exception("download_and_merge failed")
#         _set_meta(status="failed", message=str(e))
#         raise




# app/workers/tasks/download_merge.py
import os, uuid, json, math, subprocess, re
from typing import Dict, Any, Optional
from rq import get_current_job
import yt_dlp

from ...core.logging import get_logger
from ...services.storage_local import tmp_path, move_into_storage
from ...services.ffmpeg_service import merge_to_mp4_with_progress
from ...services.redis_conn import get_redis

log = get_logger(__name__)

def _publish(job, meta: dict):
    """Publish meta to Redis Pub/Sub for WS clients."""
    try:
        r = get_redis()
        payload = {"id": job.get_id(), **meta}
        r.publish(f"jobs:{job.get_id()}", json.dumps(payload))
    except Exception:
        pass

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
    _publish(job, m)

# def _ydl_download(url: str, fmt: str, outpath_noext: str, part: str) -> str:
#     """
#     Download a single format to outpath_noext (without extension).
#     Returns final absolute file path including extension.
#     Emits rich metrics via _set_meta during download.
#     """
#     def progress_hook(d):
#         if d.get("status") == "downloading":
#             try:
#                 downloaded = int(d.get("downloaded_bytes") or 0)
#                 total      = int(d.get("total_bytes") or d.get("total_bytes_estimate") or 0)
#                 speed      = float(d.get("speed") or 0.0)  # bytes/s
#                 eta        = int(d.get("eta") or 0)
#                 p = (downloaded / total) if total > 0 else 0.0
#                 _set_meta(
#                     status="downloading",
#                     progress01=max(0.01, min(0.99, p)),
#                     part=part,                         # "video" | "audio"
#                     downloadedBytes=downloaded,
#                     totalBytes=(total or None),
#                     speedBps=(speed or None),
#                     etaSeconds=(eta or None),
#                 )
#             except Exception:
#                 pass

#     ydl_opts = {
#         "quiet": True,
#         "no_warnings": True,
#         "outtmpl": outpath_noext + ".%(ext)s",
#         "format": fmt,
#         "progress_hooks": [progress_hook],
#         "noplaylist": True,
#     }
#     with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#         info = ydl.extract_info(url, download=True)
#         path = ydl.prepare_filename(info)
#         # one last emit per part (defensive)
#         try:
#             size = os.path.getsize(path)
#             _set_meta(part=part, lastPartBytes=size)
#         except Exception:
#             pass
#         return path


def _ydl_download(url: str, fmt: str, outpath_noext: str, part: str, base: float, span: float) -> str:
    def progress_hook(d):
        if d.get("status") == "downloading":
            try:
                downloaded = int(d.get("downloaded_bytes") or 0)
                total      = int(d.get("total_bytes") or d.get("total_bytes_estimate") or 0)
                speed      = float(d.get("speed") or 0.0)
                eta        = int(d.get("eta") or 0)
                p_local    = (downloaded / total) if total > 0 else 0.0
                p01        = base + span * max(0.0, min(1.0, p_local))  # MONOTONIC MAPPING
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
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)
        return path


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

def download_and_merge(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload: { url, format, title?, ext? }
    - If "format" contains "+": download parts separately and mux to mp4 with ffmpeg (copy).
    - Else: progressive direct download moved to storage.
    Returns: { path, file_name, mime, size_bytes }
    """
    url: str = payload["url"]
    fmt: str = payload["format"]              # e.g. "299+140" or "18"
    title: str = (payload.get("title") or "download").strip() or "download"
    hint_ext: Optional[str] = payload.get("ext")

    safe_title = "".join(c if c.isalnum() or c in " ._-" else "_" for c in title)
    uid = uuid.uuid4().hex[:8]

    try:
        _set_meta(status="started", progress01=0.0, message="started")

        if "+" in fmt:
            # split and download both parts with progress
            v_id, a_id = fmt.split("+", 1)
            v_tmp_base = tmp_path(f"{safe_title}-{uid}-v")
            a_tmp_base = tmp_path(f"{safe_title}-{uid}-a")

            # v_path = _ydl_download(url, v_id, v_tmp_base, part="video")
            v_path = _ydl_download(url, v_id, v_tmp_base, part="video", base=0.0, span=0.80)
            # a_path = _ydl_download(url, a_id, a_tmp_base, part="audio")
            a_path = _ydl_download(url, a_id, a_tmp_base, part="audio", base=0.80, span=0.10)

            # merging with ffmpeg + live progress
            _set_meta(status="merging", message="merging", part="merging")
            final_name = f"{safe_title}.mp4"
            out_tmp = tmp_path(f"{safe_title}-{uid}-merged.mp4")

            def on_merge_progress(p01: float, time_sec: float | None):
                _set_meta(
                    status="merging",
                    progress01=max(0.01, min(0.99, p01)),
                    part="merging",
                    mergeTimeSec=(time_sec or None),
                )

            merge_to_mp4_with_progress(v_path, a_path, out_tmp, on_progress=on_merge_progress)

            # move to storage
            final_path = move_into_storage(out_tmp, final_name)
            size_bytes = os.path.getsize(final_path)
            _set_meta(status="finished", progress01=1.0, message="done", totalBytes=size_bytes)

            return {
                "path": final_path,
                "file_name": final_name,
                "mime": _guess_mime_from_ext("mp4"),
                "size_bytes": size_bytes,
            }

        # Progressive single download
        base = tmp_path(f"{safe_title}-{uid}")
        # file_path = _ydl_download(url, fmt, base, part="progressive")
        file_path = _ydl_download(url, fmt, base, part="progressive", base=0.0, span=0.90)
        ext = (os.path.splitext(file_path)[1] or "").lstrip(".") or (hint_ext or "mp4")
        final_name = f"{safe_title}.{ext}"
        final_path = move_into_storage(file_path, final_name)
        size_bytes = os.path.getsize(final_path)

        _set_meta(status="finished", progress01=1.0, message="done",
                  totalBytes=size_bytes, part="progressive")

        return {
            "path": final_path,
            "file_name": final_name,
            "mime": _guess_mime_from_ext(ext),
            "size_bytes": size_bytes,
        }

    except Exception as e:
        log.exception("download_and_merge failed")
        _set_meta(status="failed", message=str(e))
        raise
