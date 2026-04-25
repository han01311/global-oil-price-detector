from __future__ import annotations

"""
관리자 API 엔드포인트
수집 상태 모니터링, DB 데이터 탐색, 스케줄러 제어 기능 제공.
"""
from fastapi import APIRouter, Query, HTTPException
from app.core.database import Database
from app.services.rate_limiter import RateLimiter
from app.services.scheduler import CollectionScheduler
from app.schemas.admin import (
    OverviewResponse, TableStat,
    CollectionLogsResponse, CollectionLog,
    LogStatItem,
    RateLimitStatus,
    SchedulerStatus,
    ManualTriggerRequest, ManualTriggerResponse,
    PaginatedDataResponse,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ──────────────────────────────────────────────
# Overview
# ──────────────────────────────────────────────

@router.get("/overview", response_model=OverviewResponse)
async def get_overview() -> OverviewResponse:
    """DB 테이블별 레코드 수 및 마지막 수집 시각"""
    db = Database()
    overview = await db.get_overview()
    return OverviewResponse(
        **{k: TableStat(**v) for k, v in overview.items()}
    )


# ──────────────────────────────────────────────
# Collection Logs
# ──────────────────────────────────────────────

@router.get("/logs", response_model=CollectionLogsResponse)
async def get_collection_logs(
    source: str | None = Query(default=None, description="필터: eia, fred, news 등"),
    status: str | None = Query(default=None, description="필터: success, error, rate_limited"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> CollectionLogsResponse:
    """수집 이력 조회 (필터 + 페이지네이션)"""
    db = Database()
    logs = await db.get_collection_logs(source=source, status=status, limit=limit, offset=offset)
    total = await db.get_collection_logs_count(source=source, status=status)
    return CollectionLogsResponse(
        logs=[CollectionLog(**log) for log in logs],
        total=total,
    )


@router.get("/logs/stats", response_model=list[LogStatItem])
async def get_log_stats() -> list[LogStatItem]:
    """소스별 성공/실패 통계"""
    db = Database()
    stats = await db.get_log_stats_by_source()
    return [LogStatItem(**s) for s in stats]


# ──────────────────────────────────────────────
# Data Explorer
# ──────────────────────────────────────────────

@router.get("/data/prices", response_model=PaginatedDataResponse)
async def get_prices_data(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
) -> PaginatedDataResponse:
    """유가 데이터 조회 (페이지네이션)"""
    db = Database()
    data = await db.get_oil_prices(start_date=start_date, end_date=end_date, limit=limit, offset=offset)
    total = await db.get_oil_prices_count()
    return PaginatedDataResponse(data=data, total=total, limit=limit, offset=offset)


@router.get("/data/macro", response_model=PaginatedDataResponse)
async def get_macro_data(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
) -> PaginatedDataResponse:
    """거시경제 지표 조회 (페이지네이션)"""
    db = Database()
    data = await db.get_macro_indicators(start_date=start_date, end_date=end_date, limit=limit, offset=offset)
    total = await db.get_macro_indicators_count()
    return PaginatedDataResponse(data=data, total=total, limit=limit, offset=offset)


@router.get("/data/news", response_model=PaginatedDataResponse)
async def get_news_data(
    data_source: str | None = Query(default=None, description="필터: newsapi, gnews, gdelt"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedDataResponse:
    """뉴스 기사 조회 (페이지네이션)"""
    db = Database()
    data = await db.get_news_articles(data_source=data_source, limit=limit, offset=offset)
    total = await db.get_news_articles_count(data_source=data_source)
    return PaginatedDataResponse(data=data, total=total, limit=limit, offset=offset)


@router.get("/data/inventory", response_model=PaginatedDataResponse)
async def get_inventory_data(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
) -> PaginatedDataResponse:
    """재고 데이터 조회 (페이지네이션)"""
    db = Database()
    data = await db.get_oil_inventory(start_date=start_date, end_date=end_date, limit=limit, offset=offset)
    total = await db.get_oil_inventory_count()
    return PaginatedDataResponse(data=data, total=total, limit=limit, offset=offset)


# ──────────────────────────────────────────────
# Rate Limits
# ──────────────────────────────────────────────

@router.get("/rate-limits", response_model=list[RateLimitStatus])
async def get_rate_limits() -> list[RateLimitStatus]:
    """현재 Rate Limit 사용량"""
    limiter = RateLimiter()
    status = await limiter.get_all_status()
    return [RateLimitStatus(**s) for s in status]


# ──────────────────────────────────────────────
# Manual Trigger
# ──────────────────────────────────────────────

@router.post("/collect/trigger", response_model=ManualTriggerResponse)
async def trigger_collection(request: ManualTriggerRequest) -> ManualTriggerResponse:
    """수동으로 특정 소스 수집을 트리거한다."""
    scheduler = CollectionScheduler()
    result = await scheduler.trigger_manual(request.source)
    return ManualTriggerResponse(**result)


# ──────────────────────────────────────────────
# Scheduler Control
# ──────────────────────────────────────────────

@router.get("/scheduler/status", response_model=SchedulerStatus)
async def get_scheduler_status() -> SchedulerStatus:
    """스케줄러 상태 조회"""
    scheduler = CollectionScheduler()
    status = scheduler.get_status()
    return SchedulerStatus(**status)


@router.post("/scheduler/toggle", response_model=SchedulerStatus)
async def toggle_scheduler() -> SchedulerStatus:
    """스케줄러 시작/정지 토글"""
    scheduler = CollectionScheduler()
    if scheduler.is_running:
        await scheduler.stop()
    else:
        await scheduler.start()
    status = scheduler.get_status()
    return SchedulerStatus(**status)
