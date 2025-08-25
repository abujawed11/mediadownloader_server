# placeholder for extract task
# def extract_info_task(url: str): ...
from typing import Dict, Any
from ...services.ytdlp_service import extract_info

def extract_metadata(url: str) -> Dict[str, Any]:
    """Simple wrapper so you can enqueue if needed."""
    return extract_info(url)
