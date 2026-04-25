from __future__ import annotations

"""
Admin API용 Pydantic 스키마 정의
"""
from pydantic import BaseModel


class TableStat(BaseModel):
    """테이블별 통계"""
    count: int
    last_collected: str | None = None


class OverviewResponse(BaseModel):
    """DB 전체 현황"""
    oil_prices: TableStat
    oil_inventory: TableStat
    oil_production: TableStat
    macro_indicators: TableStat
    news_articles: TableStat
    collection_logs: TableStat


class CollectionLog(BaseModel):
    """수집 이력 단건"""
    id: int
    source: str
    task_type: str
    status: str
    records_count: int = 0
    error_message: str | None = None
    started_at: str
    completed_at: str | None = None
    duration_ms: int | None = None


class CollectionLogsResponse(BaseModel):
    """수집 이력 목록"""
    logs: list[CollectionLog]
    total: int


class LogStatItem(BaseModel):
    """소스별 통계"""
    source: str
    total_runs: int
    success_count: int
    error_count: int
    rate_limited_count: int
    last_run_at: str | None = None
    total_records: int = 0


class RateLimitStatus(BaseModel):
    """Rate Limit 현황"""
    source: str
    used: int
    limit: int | None = None
    remaining: int | None = None
    last_request_at: str | None = None
    min_interval_seconds: float = 0


class SchedulerStatus(BaseModel):
    """스케줄러 상태"""
    is_running: bool
    interval_hours: int
    jobs: list[dict]


class ManualTriggerRequest(BaseModel):
    """수동 수집 트리거 요청"""
    source: str


class ManualTriggerResponse(BaseModel):
    """수동 수집 트리거 응답"""
    status: str
    message: str


class PaginatedDataResponse(BaseModel):
    """페이지네이션된 데이터 응답"""
    data: list[dict]
    total: int
    limit: int
    offset: int
