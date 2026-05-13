from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "ExamApp Server"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://exam_user:exam_pass@localhost:5432/exam_db"
    # For dev, swap to: sqlite:///./exam_dev.db

    # JWT
    JWT_SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720  # 12 hours (exam sessions can be long)

    # Face embeddings storage path (server stores enrollment embeddings)
    EMBEDDINGS_DIR: str = "./data/embeddings"

    # Snapshots (flagged frames saved here)
    SNAPSHOTS_DIR: str = "./data/snapshots"

    # WebSocket
    WS_HEARTBEAT_TIMEOUT: int = 15  # seconds before marking student disconnected

    # When true, background loop promotes SCHEDULED exams to LIVE once scheduled_start passes (UTC).
    EXAM_AUTO_SCHEDULER: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
