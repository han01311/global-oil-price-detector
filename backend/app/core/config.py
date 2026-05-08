"""
프로젝트 설정 관리
"""
import warnings
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정"""

    # 프로젝트 기본 정보
    PROJECT_NAME: str = "OilLens"
    VERSION: str = "0.2.0"
    DEBUG: bool = True
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    DATA_CACHE_DIR: str = "data"

    # PostgreSQL (primary)
    DATABASE_URL: str = "postgresql+asyncpg://petroax:petroax_dev_2026@localhost:5432/petroax"

    # Legacy — SQLite 경로 (마이그레이션 스크립트 전용)
    DATABASE_PATH: str = "data/petro_ax.db"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # 로컬 LLM 설정
    LOCAL_LLM_URL: str = "http://localhost:11434"

    # 옵셔널 API 키 (Fallback)
    GEMINI_API_KEY: Optional[str] = None
    EIA_API_KEY: str = ""
    FRED_API_KEY: str = ""

    # 선택 API 키
    NYT_API_KEY: Optional[str] = None
    GUARDIAN_API_KEY: Optional[str] = None

    # 스케줄러
    SCHEDULER_ENABLED: bool = True
    COLLECTION_INTERVAL_HOURS: int = 6

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    def __init__(self, **values):
        super().__init__(**values)
        # 필수 키 확인
        required_keys = ["EIA_API_KEY", "FRED_API_KEY"]
        missing_keys = [key for key in required_keys if not getattr(self, key)]
        if missing_keys:
            warnings.warn(
                f"Missing required environment variables: {', '.join(missing_keys)}. "
                "Some features may not work correctly."
            )


settings = Settings()
