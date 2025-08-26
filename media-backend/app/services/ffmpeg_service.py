# app/services/ffmpeg_service.py
import subprocess, re, shlex
from typing import Callable, Optional, List
import json

def _ffprobe_duration_seconds(path: str) -> Optional[float]:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1",
        path,
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8", "ignore").strip()
        return float(out) if out else None
    except Exception:
        return None

_TIME_RE = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}\.\d+)")

def _parse_time_to_seconds(line: str) -> Optional[float]:
    m = _TIME_RE.search(line)
    if not m: return None
    h, m_, s = m.groups()
    return int(h) * 3600 + int(m_) * 60 + float(s)

def merge_to_mp4_with_progress(
    video_path: str,
    audio_path: str,
    output_path: str,
    on_progress: Optional[Callable[[float, Optional[float]], None]] = None,
) -> None:
    """
    Mux video+audio into MP4 with stream copy, emitting progress based on ffmpeg 'time=' lines.
    on_progress(p01, time_sec) is called with p01 in [0..1].
    """
    # Try to estimate duration from video stream
    dur = _ffprobe_duration_seconds(video_path) or _ffprobe_duration_seconds(audio_path)
    # ffmpeg command
    cmd: List[str] = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c", "copy",
        "-movflags", "+faststart",
        "-loglevel", "info",
        output_path,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    try:
        # Parse stderr for progress lines
        if on_progress:
            on_progress(0.90, 0.0)  # jump to 90% entering merge phase
        while True:
            line = proc.stderr.readline()
            if not line:
                if proc.poll() is not None:
                    break
                continue
            t = _parse_time_to_seconds(line)
            if t is not None and dur and on_progress:
                p = 0.90 + 0.09 * max(0.0, min(1.0, t / dur))  # keep merge between 90%..99%
                on_progress(p, t)

        ret = proc.wait()
        if ret != 0:
            err = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"FFmpeg merge failed (code {ret}): {err}")
    finally:
        try:
            if on_progress:
                on_progress(0.99, dur or None)
        except Exception:
            pass
