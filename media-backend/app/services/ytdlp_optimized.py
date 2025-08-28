import os
import time
import yt_dlp
from typing import Callable, Optional
from ..core.logging import get_logger
from .storage_local import tmp_path

log = get_logger(__name__)

def download_format(url: str, format_id: str, base_filename: str, 
                   progress_callback: Optional[Callable[[float], None]] = None) -> str:
    """
    Optimized yt-dlp download for individual formats
    Returns the path to the downloaded file
    """
    output_template = tmp_path(base_filename) + ".%(ext)s"
    
    def progress_hook(d):
        if d.get("status") == "downloading" and progress_callback:
            try:
                downloaded = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                if total > 0:
                    progress = downloaded / total
                    progress_callback(progress)
            except Exception:
                pass
    
    # Optimized settings for better performance and reliability
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "outtmpl": output_template,
        "format": format_id,
        "progress_hooks": [progress_hook],
        "noplaylist": True,
        
        # Performance optimizations
        "http_chunk_size": 1048576,  # 1MB chunks (better than 10MB)
        "concurrent_fragment_downloads": 4,  # Parallel downloads
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        
        # Reliability settings
        "continue_dl": True,
        "no_check_certificates": False,
        "prefer_insecure": False,
        
        # Better user agent
        "user_agent": "Mozilla/5.0 (Android 11; Mobile; rv:88.0) Gecko/88.0 Firefox/88.0",
        
        # Optimized headers for mobile compatibility
        "headers": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none"
        }
    }
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)
                
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check for network issues
            if any(keyword in error_msg for keyword in [
                'timeout', 'connection', 'network', 'temporary'
            ]) and attempt < max_retries - 1:
                wait_time = 2 ** attempt
                log.warning(f"Network error on attempt {attempt + 1}, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
                continue
            
            log.error(f"Download failed after {attempt + 1} attempts: {e}")
            raise