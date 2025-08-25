from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import media, jobs

app = FastAPI(title="Media Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(media.router, prefix="/media", tags=["media"])
app.include_router(jobs.router, prefix="/media", tags=["jobs"])

@app.get("/health")
def health():
    return {"ok": True}
