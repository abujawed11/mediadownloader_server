# placeholder for yt-dlp logic
# implement: extract_info(url), build_formats(data), normalize pairs, etc.


# app/services/ytdlp_service.py
import os
import yt_dlp
from typing import Dict, Any, List, Optional

COOKIES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "cookies")


def _cookies_for(url: str) -> Optional[str]:
    """Return cookie file path if one exists for the platform."""
    u = url.lower()
    mapping = {
        "youtube.txt": ["youtube.com", "youtu.be"],
        "instagram.txt": ["instagram.com"],
        "facebook.txt": ["facebook.com"],
        "twitter.txt": ["twitter.com", "x.com"],
    }
    for fname, hosts in mapping.items():
        if any(h in u for h in hosts):
            path = os.path.join(COOKIES_DIR, fname)
            if os.path.exists(path):
                return path
    return None


def extract_info(url: str) -> Dict[str, Any]:
    """Run yt-dlp metadata extraction."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "bestvideo+bestaudio/best",
    }
    cookies = _cookies_for(url)
    if cookies:
        ydl_opts["cookiefile"] = cookies

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return info


def build_formats(info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Turn yt-dlp formats list into a frontend-friendly ladder."""
    formats = []
    for f in info.get("formats", []):
        if not f.get("filesize") and not f.get("filesize_approx"):
            continue
        fmt = {
            "format_id": f.get("format_id"),
            "ext": f.get("ext"),
            "filesize": f.get("filesize") or f.get("filesize_approx"),
            "vcodec": f.get("vcodec"),
            "acodec": f.get("acodec"),
            "width": f.get("width"),
            "height": f.get("height"),
            "fps": f.get("fps"),
            "format_note": f.get("format_note"),
            "url": f.get("url"),
            "is_progressive": f.get("acodec") != "none" and f.get("vcodec") != "none",
        }
        formats.append(fmt)
    return formats


def select_thumbnail(info: Dict[str, Any]) -> Optional[str]:
    """Pick a decent thumbnail if available."""
    thumbs = info.get("thumbnails") or []
    if not thumbs:
        return None
    # Prefer highest resolution
    return sorted(thumbs, key=lambda x: x.get("width") or 0)[-1].get("url")
