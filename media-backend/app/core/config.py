from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    APP_ENV: str = "dev"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    REDIS_URL: str = "redis://localhost:6379/0"

    WORK_DIR: str = "/tmp/media-work"
    OUTPUT_DIR: str = "/tmp/media-out"

    YTDLP_PLAYER_CLIENT: str = "web"
    CORS_ORIGINS: List[str] = ["http://localhost:8081"]

    class Config:
        env_file = ".env"

settings = Settings()
