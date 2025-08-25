# placeholder for ffmpeg helpers
# implement: merge_to_mp4(video_path, audio_path, out_path) using -c copy
# app/services/ffmpeg_service.py
import subprocess
from typing import List

def merge_to_mp4(video_path: str, audio_path: str, output_path: str) -> None:
    cmd: List[str] = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c", "copy",
        output_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"FFmpeg merge failed: {e.stderr.decode('utf-8', errors='ignore')}"
        )
