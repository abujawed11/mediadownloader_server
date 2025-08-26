# # app/services/ffmpeg_service.py
# import subprocess, re, shlex
# from typing import Callable, Optional, List
# import json

# def _ffprobe_duration_seconds(path: str) -> Optional[float]:
#     cmd = [
#         "ffprobe", "-v", "error",
#         "-show_entries", "format=duration",
#         "-of", "default=nw=1:nk=1",
#         path,
#     ]
#     try:
#         out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8", "ignore").strip()
#         return float(out) if out else None
#     except Exception:
#         return None

# _TIME_RE = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}\.\d+)")

# def _parse_time_to_seconds(line: str) -> Optional[float]:
#     m = _TIME_RE.search(line)
#     if not m: return None
#     h, m_, s = m.groups()
#     return int(h) * 3600 + int(m_) * 60 + float(s)

# def merge_to_mp4_with_progress(
#     video_path: str,
#     audio_path: str,
#     output_path: str,
#     on_progress: Optional[Callable[[float, Optional[float]], None]] = None,
# ) -> None:
#     """
#     Mux video+audio into MP4 with stream copy, emitting progress based on ffmpeg 'time=' lines.
#     on_progress(p01, time_sec) is called with p01 in [0..1].
#     """
#     # Try to estimate duration from video stream
#     dur = _ffprobe_duration_seconds(video_path) or _ffprobe_duration_seconds(audio_path)
#     # ffmpeg command
#     cmd: List[str] = [
#         "ffmpeg", "-y",
#         "-i", video_path,
#         "-i", audio_path,
#         "-c", "copy",
#         "-movflags", "+faststart",
#         "-loglevel", "info",
#         output_path,
#     ]
#     proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

#     try:
#         # Parse stderr for progress lines
#         if on_progress:
#             on_progress(0.90, 0.0)  # jump to 90% entering merge phase
#         while True:
#             line = proc.stderr.readline()
#             if not line:
#                 if proc.poll() is not None:
#                     break
#                 continue
#             t = _parse_time_to_seconds(line)
#             if t is not None and dur and on_progress:
#                 p = 0.90 + 0.09 * max(0.0, min(1.0, t / dur))  # keep merge between 90%..99%
#                 on_progress(p, t)

#         ret = proc.wait()
#         if ret != 0:
#             err = proc.stderr.read() if proc.stderr else ""
#             raise RuntimeError(f"FFmpeg merge failed (code {ret}): {err}")
#     finally:
#         try:
#             if on_progress:
#                 on_progress(0.99, dur or None)
#         except Exception:
#             pass



# app/services/ffmpeg_service.py
# import subprocess, re
# from typing import Callable, Optional, List, Literal

# Container = Literal["mp4", "webm", "mkv"]

# def _ffprobe_duration_seconds(path: str) -> Optional[float]:
#     cmd = [
#         "ffprobe", "-v", "error",
#         "-show_entries", "format=duration",
#         "-of", "default=nw=1:nk=1",
#         path,
#     ]
#     try:
#         out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8", "ignore").strip()
#         return float(out) if out else None
#     except Exception:
#         return None

# _TIME_RE = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}\.\d+)")

# def _parse_time_to_seconds(line: str) -> Optional[float]:
#     m = _TIME_RE.search(line)
#     if not m:
#         return None
#     h, m_, s = m.groups()
#     return int(h) * 3600 + int(m_) * 60 + float(s)

# def merge_with_progress_copy(
#     video_path: str,
#     audio_path: str,
#     output_path: str,
#     container: Container,
#     on_progress: Optional[Callable[[float, Optional[float]], None]] = None,
# ) -> None:
#     """
#     Stream-copy mux into the chosen container, emitting progress based on ffmpeg stderr 'time='.
#     Keeps merge phase between 90%..99%.
#     """
#     dur = _ffprobe_duration_seconds(video_path) or _ffprobe_duration_seconds(audio_path)

#     # container-specific flags
#     extra: List[str] = []
#     if container == "mp4":
#         extra += ["-movflags", "+faststart"]  # nice-to-have for mp4
#     # webm/mkv: no special flags needed for copy

#     cmd: List[str] = [
#         "ffmpeg", "-y",
#         "-i", video_path,
#         "-i", audio_path,
#         "-c", "copy",
#         "-shortest",
#         *extra,
#         "-loglevel", "info",
#         output_path,
#     ]

#     proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
#     try:
#         if on_progress:
#             on_progress(0.90, 0.0)
#         while True:
#             line = proc.stderr.readline()
#             if not line:
#                 if proc.poll() is not None:
#                     break
#                 continue
#             t = _parse_time_to_seconds(line)
#             if t is not None and dur and on_progress:
#                 p = 0.90 + 0.09 * max(0.0, min(1.0, t / dur))
#                 on_progress(p, t)

#         ret = proc.wait()
#         if ret != 0:
#             err = proc.stderr.read() if proc.stderr else ""
#             raise RuntimeError(f"FFmpeg merge failed (code {ret}): {err}")
#     finally:
#         try:
#             if on_progress:
#                 on_progress(0.99, dur or None)
#         except Exception:
#             pass




# app/services/ffmpeg_service.py
import subprocess, re, json, os, shlex, time
from typing import Callable, Optional, List, Dict, Any, Literal
from ..core.logging import get_logger

log = get_logger(__name__)

Container = Literal["mp4", "webm", "mkv"]

_TIME_RE = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}\.\d+)")

def _parse_time_to_seconds(line: str) -> Optional[float]:
    m = _TIME_RE.search(line)
    if not m:
        return None
    h, m_, s = m.groups()
    return int(h) * 3600 + int(m_) * 60 + float(s)

def _run_check_output(cmd: List[str]) -> str:
    return subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8", "ignore")

def ffprobe_basic(path: str) -> Dict[str, Any]:
    """
    Return a tiny dict: {container, duration, vcodec, acodec, width, height}
    """
    log.info("[ffprobe] path=%s", path)
    try:
        out = _run_check_output([
            "ffprobe", "-v", "error",
            "-print_format", "json",
            "-show_format", "-show_streams",
            path
        ])
        j = json.loads(out)
    except Exception as e:
        log.error("[ffprobe] failed for %s: %s", path, e)
        return {"error": f"ffprobe failed: {e}", "raw": None}

    fmt = (j.get("format") or {})
    streams = j.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), {})

    res = {
        "container": (fmt.get("format_name") or "").split(",")[0],
        "duration": float(fmt.get("duration")) if fmt.get("duration") else None,
        "vcodec": v.get("codec_name"),
        "acodec": a.get("codec_name"),
        "width": v.get("width"),
        "height": v.get("height"),
    }
    log.info("[ffprobe] summary=%s", json.dumps(res))
    return res

def merge_with_progress_copy(
    video_path: str,
    audio_path: str,
    output_path: str,
    container: Container,
    on_progress: Optional[Callable[[float, Optional[float]], None]] = None,
    on_debug: Optional[Callable[[str], None]] = None,
    stderr_log_path: Optional[str] = None,
) -> None:
    """
    Stream-copy mux into the chosen container.
    Emits:
      - progress (kept in 90..99%)
      - rolling debug lines (stderr tail)
      - writes full stderr to stderr_log_path if provided
    Raises RuntimeError on failure with the last stderr chunk.
    """
    vprobe = ffprobe_basic(video_path)
    aprobe = ffprobe_basic(audio_path)
    dur = (vprobe.get("duration") or aprobe.get("duration") or None)

    log.info("[merge] container=%s out=%s", container, output_path)
    log.info("[merge] inputs: video=%s audio=%s", video_path, audio_path)

    extra: List[str] = []
    if container == "mp4":
        extra += ["-movflags", "+faststart"]

    cmd: List[str] = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c", "copy",
        "-shortest",
        *extra,
        "-loglevel", "info",
        output_path,
    ]
    log.info("[merge] cmd=%s", " ".join(shlex.quote(p) for p in cmd))

    log_fh = open(stderr_log_path, "w", encoding="utf-8") if stderr_log_path else None
    tail: List[str] = []
    last_log_ts = 0.0

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        if on_progress:
            on_progress(0.90, 0.0)

        while True:
            line = proc.stderr.readline()
            if not line:
                if proc.poll() is not None:
                    break
                continue

            if log_fh:
                log_fh.write(line)

            # keep rolling tail (last 50 lines)
            tail.append(line.rstrip())
            if len(tail) > 50:
                tail.pop(0)

            # throttle logging of progress-ish lines to ~1/sec
            t = _parse_time_to_seconds(line)
            now = time.time()
            if t is not None and dur and on_progress:
                p = 0.90 + 0.09 * max(0.0, min(1.0, t / dur))
                on_progress(p, t)
                if now - last_log_ts > 1.0:
                    log.info("[merge] progress t=%.2fs p=%.1f%%", t, p * 100.0)
                    last_log_ts = now
            elif ("Stream mapping" in line) or ("muxing" in line):
                log.info("[merge] %s", line.strip())

        ret = proc.wait()
        if ret != 0:
            last = "\n".join(tail[-12:])
            log.error("[merge] ffmpeg failed (code %s)\n%s", ret, last)
            raise RuntimeError(f"FFmpeg merge failed (code {ret})\n{last}")

        log.info("[merge] success out=%s", output_path)

    finally:
        if log_fh:
            try:
                log_fh.flush()
                log_fh.close()
            except Exception:
                pass
        try:
            if on_progress:
                on_progress(0.99, dur or None)
        except Exception:
            pass
