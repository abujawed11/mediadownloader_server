from fastapi import APIRouter

router = APIRouter()

@router.get("/info")
def info():
    # TODO: wire to yt-dlp extract_info
    return {"msg": "info endpoint placeholder"}

@router.post("/direct-url")
def direct_url():
    # TODO: return progressive URL + http_headers for RNBD
    return {"msg": "direct-url placeholder"}
