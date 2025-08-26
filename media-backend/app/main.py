from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import get_settings
from .api.routes.media import router as media_router
from .api.routes.jobs import router as jobs_router
from .api.routes.jobs_ws import router as jobs_ws_router  # NEW
from .api.routes.jobs_bus import router as jobs_bus_router  # NEW

def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.APP_NAME)

    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=86400,
    )

    @app.get("/health")
    def health():
        return {"ok": True}

    app.include_router(media_router)
    app.include_router(jobs_router)
    app.include_router(jobs_ws_router)  # NEW
    app.include_router(jobs_bus_router)  # NEW
    return app

app = create_app()
