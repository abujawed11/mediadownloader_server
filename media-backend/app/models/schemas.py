from pydantic import BaseModel
from typing import Any, Dict, List, Optional

class InfoRequest(BaseModel):
    url: str

class FormatItem(BaseModel):
    itag: str
    ext: str
    height: Optional[int] = None
    fps: Optional[int] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    container: Optional[str] = None
    sizeBytes: Optional[int] = None
    isProgressive: bool = False
    isMerge: bool = False
    display: str

class InfoResponse(BaseModel):
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    formats: List[Dict[str, Any]]
