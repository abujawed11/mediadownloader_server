import os
from pydantic import BaseModel, Field
from functools import lru_cache
from typing import Optional


class Settings(BaseModel):
    APP_NAME: str = "Media Backend"
    ENV: str = Field(default=os.getenv("ENV", "dev"))
    HOST: str = Field(default=os.getenv("HOST", "0.0.0.0"))
    PORT: int = Field(default=int(os.getenv("PORT", "8000")))

    REDIS_URL: str = Field(default=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    RQ_QUEUE: str = Field(default=os.getenv("RQ_QUEUE", "media"))
    RQ_JOB_TTL: int = Field(default=int(os.getenv("RQ_JOB_TTL", "86400")))  # 1 day
    RQ_RESULT_TTL: int = Field(default=int(os.getenv("RQ_RESULT_TTL", "604800")))  # 7 days
    RQ_FAILURE_TTL: int = Field(default=int(os.getenv("RQ_FAILURE_TTL", "604800")))

    STORAGE_DIR: str = Field(default=os.getenv("STORAGE_DIR", "./storage"))
    TMP_DIR: str = Field(default=os.getenv("TMP_DIR", "./.tmp"))

    # CORS
    CORS_ORIGINS: str = Field(default=os.getenv("CORS_ORIGINS", "*"))  # comma-separated

    # Optional public base to build file links later (CDN, Nginx, etc.)
    PUBLIC_BASE_URL: Optional[str] = Field(default=os.getenv("PUBLIC_BASE_URL"))


@lru_cache()
def get_settings() -> Settings:
    s = Settings()
    os.makedirs(s.STORAGE_DIR, exist_ok=True)
    os.makedirs(s.TMP_DIR, exist_ok=True)
    return s
