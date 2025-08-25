# save files locally to OUTPUT_DIR
# implement: save_temp, promote, build_file_response
import os
import shutil
from typing import Optional, Tuple
from ..core.config import get_settings

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def storage_path(filename: str) -> str:
    s = get_settings()
    ensure_dir(s.STORAGE_DIR)
    return os.path.join(s.STORAGE_DIR, filename)

def tmp_path(filename: str) -> str:
    s = get_settings()
    ensure_dir(s.TMP_DIR)
    return os.path.join(s.TMP_DIR, filename)

def move_into_storage(src_path: str, dest_filename: str) -> str:
    dest = storage_path(dest_filename)
    ensure_dir(os.path.dirname(dest))
    shutil.move(src_path, dest)
    return dest

def public_url_for(filename: str) -> Optional[str]:
    base = get_settings().PUBLIC_BASE_URL
    if not base:
        return None
    base = base.rstrip("/")
    return f"{base}/{filename}"
