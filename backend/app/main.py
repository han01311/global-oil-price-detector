"""
FastAPI 메인 애플리케이션
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """헬스체크 엔드포인트"""
    required_keys = ["GEMINI_API_KEY", "EIA_API_KEY", "FRED_API_KEY"]
    missing_keys = [key for key in required_keys if not getattr(settings, key)]
    
    config_status = "ok"
    if missing_keys:
        config_status = f"missing_required_keys: {', '.join(missing_keys)}"

    return {
        "status": "ok", 
        "version": settings.VERSION,
        "config_status": config_status
    }
