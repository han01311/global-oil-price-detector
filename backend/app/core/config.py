"""
프로젝트 설정 관리
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """애플리케이션 설정"""

    # 프로젝트 기본 정보
    PROJECT_NAME: str = "New Project"
    VERSION: str = "0.1.0"
    DEBUG: bool = True

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # API 키
    GEMINI_API_KEY: str = ""

    # 데이터베이스 (추후 설정)
    DATABASE_URL: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
