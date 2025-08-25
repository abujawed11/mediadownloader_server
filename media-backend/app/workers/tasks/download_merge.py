# placeholder for download + merge task
# def download_merge_task(url: str, fmt_selector: str, title_hint: str = ""): ...
import os
import yt_dlp
import uuid
from typing import Dict, Any, Optional, Tuple
from rq import get_current_job

from ...core.logging import get_logger
from ...services.storage_local import tmp_path, move_into_storage
from ...services.ffmpeg_service import merge_to_mp4

log = get_logger(__name__)


def _set_meta(status: str = None, progress: float = None, message: str = None):
    job = get_current_job()
    if not job:
        return
    if status is not None:
        job.meta["status"] = status
    if progress is not None:
        job.meta["progress01"] = float(progress)
    if message is not None:
        job.meta["message"] = message
    job.save_meta()


def _ydl_download(url: str, fmt: str, outpath: str) -> str:
    """
    Download a single format to the given path (without extension).
    Returns the final absolute file path including extension.
    """
    def progress_hook(d):
        if d.get("status") == "downloading":
            # best-effort normalized progress
            try:
                p = float(d.get("downloaded_bytes", 0)) / float(d.get("total_bytes", d.get("total_bytes_estimate", 1)))
                _set_meta(status="downloading", progress=max(0.01, min(0.99, p)))
            except Exception:
                pass

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "outtmpl": outpath + ".%(ext)s",
        "format": fmt,
        "progress_hooks": [progress_hook],
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        res = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(res)  # actual file path


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
    - If format contains "+": download parts separately and mux with ffmpeg -c copy to mp4.
    - Else: progressive; download directly and move into storage.
    Returns: { path, file_name, mime, size_bytes }
    """
    url: str = payload["url"]
    fmt: str = payload["format"]              # e.g. "299+140" or "18"
    title: str = (payload.get("title") or "download").strip() or "download"
    hint_ext: Optional[str] = payload.get("ext")

    safe_title = "".join(c if c.isalnum() or c in " ._-" else "_" for c in title)
    uid = uuid.uuid4().hex[:8]

    try:
        _set_meta(status="started", progress=0.0, message="started")

        if "+" in fmt:
            # Download video & audio separately
            v_id, a_id = fmt.split("+", 1)
            v_tmp_base = tmp_path(f"{safe_title}-{uid}-v")
            a_tmp_base = tmp_path(f"{safe_title}-{uid}-a")
            v_path = _ydl_download(url, v_id, v_tmp_base)
            a_path = _ydl_download(url, a_id, a_tmp_base)

            _set_meta(status="merging", message="merging")

            # Final container = mp4 (works for most sites when codecs are H.264/AAC)
            final_name = f"{safe_title}.mp4"
            out_tmp = tmp_path(f"{safe_title}-{uid}-merged.mp4")
            merge_to_mp4(v_path, a_path, out_tmp)

            # Move to storage
            final_path = move_into_storage(out_tmp, final_name)
            size_bytes = os.path.getsize(final_path)
            mime = _guess_mime_from_ext("mp4")

            _set_meta(status="finished", progress=1.0, message="done")

            return {
                "path": final_path,
                "file_name": final_name,
                "mime": mime,
                "size_bytes": size_bytes,
            }

        # Progressive single download
        base = tmp_path(f"{safe_title}-{uid}")
        file_path = _ydl_download(url, fmt, base)
        ext = (os.path.splitext(file_path)[1] or "").lstrip(".") or (hint_ext or "mp4")
        final_name = f"{safe_title}.{ext}"
        final_path = move_into_storage(file_path, final_name)
        size_bytes = os.path.getsize(final_path)
        mime = _guess_mime_from_ext(ext)

        _set_meta(status="finished", progress=1.0, message="done")

        return {
            "path": final_path,
            "file_name": final_name,
            "mime": mime,
            "size_bytes": size_bytes,
        }

    except Exception as e:
        log.exception("download_and_merge failed")
        _set_meta(status="failed", message=str(e))
        raise
