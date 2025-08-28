# app/api/routes/media.py
from fastapi import APIRouter, HTTPException
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from ...models.schemas import (
    InfoRequest,          # { url: str }
    InfoResponse,         # { title: str, thumbnail: Optional[str], duration: Optional[int], formats: List[FormatOption] }
    DirectUrlRequest,     # { url: str, format_id: str }
    DirectUrlResponse,    # { url: str, headers?: Dict[str,str], mime?: str, fileName?: str }
    FormatOption,         # { format_string: str, label: str, ext?: str, note?: str, sizeBytes?: Optional[int] }
)
from ...services.ytdlp_service import extract_info
from ...core.logging import get_logger

router = APIRouter(prefix="/media", tags=["media"])
log = get_logger(__name__)


# -------- helpers to build frontend-friendly ladders --------

def _fmt_label(
    width: Optional[int],
    height: Optional[int],
    fps: Optional[float],
    ext: Optional[str],
    is_merge: bool,
    note: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """Build a concise display label and a secondary note."""
    p = f"{height}p" if height else (f"{width}w" if width else "")
    if fps and fps >= 50:
        p = f"{p}{int(fps)}" if p else f"{int(fps)}fps"
    base = p or (note or ext or "unknown")
    base = base.upper() if base in ("mp3", "m4a", "aac") else base
    label = f"{base} • {ext.upper()}" if ext else base
    if is_merge:
        label = f"{label} • merge"
    return label, note


def _choose_best_audio(audios: List[Dict[str, Any]], family: str) -> Optional[Dict[str, Any]]:
    """
    Pick best audio for a container 'family':
      - 'mp4' prefers m4a/aac
      - 'webm' prefers webm/opus
    """
    if not audios:
        return None

    def bitrate_of(f: Dict[str, Any]) -> int:
        # Prefer 'tbr' (total bitrate). Fall back to 'abr' or 0.
        return int((f.get("tbr") or f.get("abr") or 0) * 1000)

    if family == "mp4":
        cand = [a for a in audios if (a.get("ext") in {"m4a", "mp4"} or "aac" in str(a.get("acodec") or ""))]
        cand = cand or audios
        return max(cand, key=bitrate_of)
    else:
        cand = [a for a in audios if (a.get("ext") in {"webm"} or "opus" in str(a.get("acodec") or ""))]
        cand = cand or audios
        return max(cand, key=bitrate_of)


def _safe_int(n: Any) -> Optional[int]:
    try:
        return int(n) if n is not None else None
    except Exception:
        return None


def _approx_size(f: Dict[str, Any]) -> Optional[int]:
    return _safe_int(f.get("filesize") or f.get("filesize_approx"))


def _estimate_merged_size(video: Dict[str, Any], audio: Dict[str, Any], duration: Optional[int] = None) -> Optional[int]:
    """Better size estimation for merged video+audio streams."""
    v_size = _approx_size(video)
    a_size = _approx_size(audio)
    
    # If we have both sizes, use them but add 15% overhead for container
    if v_size and a_size:
        return int((v_size + a_size) * 1.15)
    
    # Fallback: estimate based on bitrates and duration if available
    if duration:
        v_tbr = video.get("tbr") or video.get("vbr") or 0
        a_tbr = audio.get("tbr") or audio.get("abr") or 0
        
        if v_tbr and a_tbr:
            # Convert kbps to bytes per second, multiply by duration, add 20% overhead
            total_bps = (v_tbr + a_tbr) * 1000 / 8  # kbps to bytes per second
            estimated = int(total_bps * duration * 1.2)
            return estimated
    
    # Last resort: use available size or return None
    return v_size or a_size


def _family_from_ext(ext: Optional[str]) -> Optional[str]:
    if not ext:
        return None
    if ext in {"mp4", "m4v", "m4a"}:
        return "mp4"
    if ext in {"webm"}:
        return "webm"
    return None


def _ladder_from_info(info: Dict[str, Any]) -> List[FormatOption]:
    """
    Builds a list of FormatOption objects with improved prioritization:
      - Progressive formats (video+audio) - PRIORITIZED for better UX
      - Merge formats (video-only + chosen best audio) with better size estimation
    """
    raw = info.get("formats") or []
    out: List[FormatOption] = []
    duration = _safe_int(info.get("duration"))

    videos_only = []
    audios_only = []
    progressive = []

    for f in raw:
        vcodec = str(f.get("vcodec") or "none")
        acodec = str(f.get("acodec") or "none")
        has_v = vcodec != "none"
        has_a = acodec != "none"

        item = {
            "format_id": f.get("format_id"),
            "ext": f.get("ext"),
            "width": f.get("width"),
            "height": f.get("height"),
            "fps": f.get("fps"),
            "format_note": f.get("format_note"),
            "filesize": _approx_size(f),
            "url": f.get("url"),
            "mime_type": f.get("mime_type"),
            "vcodec": vcodec,
            "acodec": acodec,
            "tbr": f.get("tbr"),
            "abr": f.get("abr"),
            "vbr": f.get("vbr"),
        }

        if has_v and has_a:
            progressive.append(item)
        elif has_v and not has_a:
            videos_only.append(item)
        elif has_a and not has_v:
            audios_only.append(item)

    # Progressive options (direct) - PRIORITIZED and marked clearly
    for f in progressive:
        label, note = _fmt_label(f.get("width"), f.get("height"), f.get("fps"), f.get("ext"), False, f.get("format_note"))
        # Add "direct" indicator to show these don't need merging
        label = f"{label} • direct"
        out.append(
            FormatOption(
                format_string=str(f.get("format_id")),
                label=label,
                ext=f.get("ext") or "mp4",
                note=note or "no merge required",
                sizeBytes=_approx_size(f),
            )
        )

    # Merge options: pair each video-only with a best-matching audio
    for v in videos_only:
        fam = _family_from_ext(v.get("ext"))
        if not fam:
            continue
        best_a = _choose_best_audio(audios_only, fam)
        if not best_a:
            continue

        # Use improved size estimation
        better_size = _estimate_merged_size(v, best_a, duration)
        
        label, note = _fmt_label(v.get("width"), v.get("height"), v.get("fps"), v.get("ext"), True, v.get("format_note"))
        fmt_string_ui = f"{v['format_id']}+{best_a['format_id']}-drc"

        out.append(
            FormatOption(
                format_string=fmt_string_ui,
                label=label,
                ext=(v.get("ext") or "mp4"),
                note=note or "merge required",
                sizeBytes=better_size,
            )
        )

    # Improved sorting: Progressive first, then by quality
    def sort_key(o: FormatOption):
        # Progressive formats get priority (lower sort value)
        is_progressive = "direct" in o.label
        priority = 0 if is_progressive else 1
        
        # Extract height for quality sorting
        h = 0
        try:
            if "p" in o.label:
                h = int(o.label.split("p")[0].split()[-1])
        except Exception:
            h = 0
            
        # Extract fps
        fps = 0
        if "p60" in o.label or "60" in o.label:
            fps = 60
            
        return (priority, -h, -fps, -(o.sizeBytes or 0))

    out.sort(key=sort_key)
    return out


# ---------------------- Routes ----------------------

@router.post("/info", response_model=InfoResponse)
def info(body: InfoRequest) -> InfoResponse:
    """
    Return metadata + frontend-friendly formats (progressive + merge ladders).
    """
    try:
        data = extract_info(body.url)
        title: str = data.get("title") or "Untitled"
        duration: Optional[int] = _safe_int(data.get("duration"))
        # Pick largest thumbnail if present
        thumb = None
        thumbs = data.get("thumbnails") or []
        if thumbs:
            thumb = sorted(thumbs, key=lambda x: x.get("width") or 0)[-1].get("url")

        formats = _ladder_from_info(data)
        return InfoResponse(
            title=title,
            thumbnail=thumb,
            duration=duration,
            formats=formats,
        )
    except Exception as e:
        log.exception("info() failed")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/direct-url", response_model=DirectUrlResponse)
def direct_url(body: DirectUrlRequest) -> DirectUrlResponse:
    """
    For progressive formats only:
      - Returns a direct media URL and optional headers so the RN app can download directly.
      - If a merge format_id like "299+140" is sent, respond 409 to force client to use the job flow.
    """
    # Reject merged selections here — use your RQ/worker job flow instead.
    if "+" in (body.format_id or ""):
        raise HTTPException(status_code=409, detail="Selected format requires server merge")

    try:
        info = extract_info(body.url)

        # Find the matching progressive format by format_id
        raw_formats = info.get("formats") or []
        target: Optional[Dict[str, Any]] = None
        for f in raw_formats:
            if str(f.get("format_id")) == str(body.format_id):
                vcodec = str(f.get("vcodec") or "none")
                acodec = str(f.get("acodec") or "none")
                if vcodec != "none" and acodec != "none":  # ensure progressive
                    target = f
                break

        if not target:
            raise HTTPException(status_code=404, detail="Progressive format not found")

        # yt-dlp often provides usable direct URLs. Some sites may need headers.
        direct_url = target.get("url")
        if not direct_url:
            raise HTTPException(status_code=400, detail="No direct URL available for this format")

        # Headers: per-format or top-level http headers if present
        headers = {}
        # format-level headers (rare but supported)
        if isinstance(target.get("http_headers"), dict):
            headers.update({str(k): str(v) for k, v in target["http_headers"].items()})
        # top-level
        if isinstance(info.get("http_headers"), dict):
            headers.update({str(k): str(v) for k, v in info["http_headers"].items()})

        # MIME and filename hint
        mime = target.get("mime_type")
        title = (info.get("title") or "download").replace("/", "_").replace("\\", "_")
        ext = target.get("ext") or ("webm" if (mime and "webm" in mime) else "mp4")
        file_name = f"{title}.{ext}"

        return DirectUrlResponse(
            url=direct_url,
            headers=(headers or None),
            mime=mime,
            fileName=file_name,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception("direct_url() failed")
        raise HTTPException(status_code=400, detail=str(e))
