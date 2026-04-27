from __future__ import annotations

"""
FastAPI 메인 애플리케이션
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Database
from app.services.scheduler import CollectionScheduler
from app.api import prices, news, forecast, briefing, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 수명주기 관리: DB 연결 + 스케줄러 시작/종료"""
    # Startup
    db = Database()
    await db.connect()

    scheduler = CollectionScheduler()
    if settings.SCHEDULER_ENABLED:
        await scheduler.start()

    yield

    # Shutdown
    await scheduler.stop()
    await db.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(prices.router)
app.include_router(news.router)
app.include_router(forecast.router)
app.include_router(briefing.router)
app.include_router(admin.router)

@app.get("/api/health")
async def health_check():
    """헬스체크 엔드포인트"""
    required_keys = ["GEMINI_API_KEY", "EIA_API_KEY", "FRED_API_KEY"]
    missing_keys = [key for key in required_keys if not getattr(settings, key)]
    
    config_status = "ok"
    if missing_keys:
        config_status = f"missing_required_keys: {', '.join(missing_keys)}"

    scheduler = CollectionScheduler()

    return {
        "status": "ok", 
        "version": settings.VERSION,
        "config_status": config_status,
        "scheduler_running": scheduler.is_running,
        "database": "postgresql",
    }
