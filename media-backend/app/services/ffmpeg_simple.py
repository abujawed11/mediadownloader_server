import subprocess
import time
import re
from typing import Optional, Callable
from ..core.logging import get_logger

log = get_logger(__name__)

TIME_REGEX = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}\.\d+)")

def parse_time_to_seconds(line: str) -> Optional[float]:
    """Extract time in seconds from FFmpeg output"""
    match = TIME_REGEX.search(line)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

def get_duration(file_path: str) -> Optional[float]:
    """Get file duration using ffprobe"""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception as e:
        log.warning(f"Failed to get duration for {file_path}: {e}")
    return None

def merge_simple_reliable(video_path: str, audio_path: str, output_path: str,
                         progress_callback: Optional[Callable[[float], None]] = None):
    """
    Simple, reliable FFmpeg merge using stream copy
    Uses conservative settings that work across all formats
    """
    log.info(f"Merging: {video_path} + {audio_path} -> {output_path}")
    
    # Get duration for progress tracking
    duration = get_duration(video_path) or get_duration(audio_path)
    
    # Simple, reliable command that works with most formats
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c", "copy",  # Stream copy - no re-encoding
        "-shortest",   # Stop when shortest stream ends
        "-avoid_negative_ts", "make_zero",  # Handle timestamp issues
        "-fflags", "+genpts",  # Generate presentation timestamps
        "-loglevel", "info",
        output_path
    ]
    
    log.info(f"FFmpeg command: {' '.join(cmd)}")
    
    start_time = time.time()
    process = subprocess.Popen(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, 
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    try:
        last_progress_time = 0
        
        while True:
            line = process.stderr.readline()
            if not line:
                if process.poll() is not None:
                    break
                time.sleep(0.1)
                continue
            
            # Parse progress
            current_time = parse_time_to_seconds(line)
            if current_time is not None and duration and progress_callback:
                progress = min(1.0, current_time / duration)
                now = time.time()
                
                # Throttle progress updates to once per second
                if now - last_progress_time >= 1.0:
                    progress_callback(progress)
                    last_progress_time = now
                    log.info(f"Merge progress: {progress*100:.1f}% ({current_time:.1f}s/{duration:.1f}s)")
            
            # Log important messages
            if any(keyword in line for keyword in ["error", "failed", "invalid"]):
                log.warning(f"FFmpeg: {line.strip()}")
        
        return_code = process.wait(timeout=300)  # 5 minute timeout
        
        if return_code != 0:
            stderr_output = process.stderr.read()
            error_msg = f"FFmpeg failed with code {return_code}: {stderr_output}"
            log.error(error_msg)
            raise RuntimeError(error_msg)
        
        elapsed = time.time() - start_time
        log.info(f"Merge completed successfully in {elapsed:.2f} seconds")
        
        if progress_callback:
            progress_callback(1.0)
            
    except subprocess.TimeoutExpired:
        process.kill()
        log.error("FFmpeg merge timed out")
        raise RuntimeError("Merge operation timed out")
    except Exception as e:
        process.kill()
        log.error(f"Merge failed: {e}")
        raise