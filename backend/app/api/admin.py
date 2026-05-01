from __future__ import annotations
from datetime import datetime, timezone

"""
관리자 API 엔드포인트
수집 상태 모니터링, DB 데이터 탐색, 스케줄러 제어 기능 제공.
"""
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from sqlalchemy import select, func, text
from app.core.database import Database
from app.models.base import get_session_factory
from pydantic import BaseModel
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


@router.get("/data/production", response_model=PaginatedDataResponse)
async def get_production_data(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
) -> PaginatedDataResponse:
    """생산량 데이터 조회 (페이지네이션)"""
    db = Database()
    data = await db.get_oil_production(start_date=start_date, end_date=end_date, limit=limit, offset=offset)
    total = await db.get_oil_production_count()
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


# ──────────────────────────────────────────────
# Crawl Control (History Crawl)
# ──────────────────────────────────────────────

import asyncio
import subprocess
import signal
import sys
import os

# 크롤링 프로세스 상태를 메모리에 관리
_crawl_state = {
    "is_running": False,
    "process": None,
    "output_lines": [],
    "started_at": None,
    "target": 0,
    "current_year": None,
    "collected": 0,
    # v2 확장 필드
    "year_start": None,
    "year_end": None,
    "years_total": 0,
    "years_completed": 0,
    "current_source": None,
    "nyt_collected": 0,
    "guardian_collected": 0,
    "dupes_removed": 0,
    "elapsed_seconds": 0,
}


@router.post("/crawl/start")
async def start_crawl(target: int = 2000, start_year: int | None = None, end_year: int | None = None):
    """과거 기사 크롤링 시작 (범위 수집 / 단독 수집 지원)"""
    global _crawl_state
    if _crawl_state["is_running"]:
        return {"status": "already_running", "message": "크롤러가 이미 실행 중입니다."}

    script_path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "crawl_history.py")
    cmd = [sys.executable, script_path, "--target", str(target)]
    if start_year:
        cmd.extend(["--start", str(start_year)])
    if end_year:
        cmd.extend(["--end", str(end_year)])

    import threading
    import json as _json

    _crawl_state["is_running"] = True
    _crawl_state["output_lines"] = []
    _crawl_state["started_at"] = datetime.now(timezone.utc).isoformat()
    _crawl_state["target"] = target
    _crawl_state["collected"] = 0
    _crawl_state["current_year"] = start_year or 2000
    _crawl_state["year_start"] = start_year or 2000
    _crawl_state["year_end"] = end_year
    _crawl_state["years_total"] = 0
    _crawl_state["years_completed"] = 0
    _crawl_state["current_source"] = None
    _crawl_state["nyt_collected"] = 0
    _crawl_state["guardian_collected"] = 0
    _crawl_state["dupes_removed"] = 0
    _crawl_state["elapsed_seconds"] = 0
    _crawl_state["year_breakdown"] = []

    def run_crawl():
        global _crawl_state
        import re
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
            )
            _crawl_state["process"] = proc

            for line in iter(proc.stdout.readline, ''):
                line = line.strip()
                if not line:
                    continue

                _crawl_state["output_lines"].append(line)
                if len(_crawl_state["output_lines"]) > 100:
                    _crawl_state["output_lines"] = _crawl_state["output_lines"][-100:]

                # JSON 라인 파싱 (구조화된 진행 정보)
                try:
                    msg = _json.loads(line)
                    msg_type = msg.get("type")
                    if msg_type == "start":
                        _crawl_state["year_start"] = msg.get("year_start")
                        _crawl_state["year_end"] = msg.get("year_end")
                        _crawl_state["years_total"] = msg.get("years_total", 0)
                    elif msg_type == "progress":
                        _crawl_state["current_year"] = msg.get("year")
                        _crawl_state["current_source"] = msg.get("source")
                        _crawl_state["elapsed_seconds"] = msg.get("elapsed_sec", 0)
                    elif msg_type == "year_done":
                        _crawl_state["current_year"] = msg.get("year")
                        _crawl_state["collected"] = msg.get("total_collected", 0)
                        _crawl_state["years_completed"] = msg.get("years_completed", 0)
                        _crawl_state["nyt_collected"] = _crawl_state.get("nyt_collected", 0) + msg.get("nyt", 0)
                        _crawl_state["guardian_collected"] = _crawl_state.get("guardian_collected", 0) + msg.get("guardian", 0)
                        _crawl_state["dupes_removed"] = _crawl_state.get("dupes_removed", 0) + msg.get("dupes_removed", 0)
                        _crawl_state["elapsed_seconds"] = msg.get("elapsed_sec", 0)
                        _crawl_state["current_source"] = None
                        if "year_breakdown" in msg:
                            _crawl_state["year_breakdown"] = msg["year_breakdown"]
                    elif msg_type == "year_empty":
                        _crawl_state["years_completed"] = msg.get("years_completed", 0)
                        if "year_breakdown" in msg:
                            _crawl_state["year_breakdown"] = msg["year_breakdown"]
                    elif msg_type in ("complete", "target_reached"):
                        _crawl_state["collected"] = msg.get("total_collected", _crawl_state["collected"])
                        _crawl_state["nyt_collected"] = msg.get("total_nyt", _crawl_state.get("nyt_collected", 0))
                        _crawl_state["guardian_collected"] = msg.get("total_guardian", _crawl_state.get("guardian_collected", 0))
                        _crawl_state["dupes_removed"] = msg.get("total_dupes", _crawl_state.get("dupes_removed", 0))
                        _crawl_state["elapsed_seconds"] = msg.get("elapsed_sec", 0)
                        if "year_breakdown" in msg:
                            _crawl_state["year_breakdown"] = msg["year_breakdown"]
                    continue
                except (ValueError, TypeError):
                    pass

                # 레거시 파싱
                year_match = re.search(r'📰\s*(\d{4})년.*누적\s*(\d+)', line)
                if year_match:
                    _crawl_state["current_year"] = int(year_match.group(1))
                    _crawl_state["collected"] = int(year_match.group(2))

            proc.wait()
        except Exception as e:
            _crawl_state["output_lines"].append(f"ERROR: {str(e)}")
        finally:
            _crawl_state["is_running"] = False
            _crawl_state["process"] = None

    thread = threading.Thread(target=run_crawl, daemon=True)
    thread.start()

    year_desc = f"{start_year or 2000}"
    if end_year:
        year_desc += f"~{end_year}"
    return {"status": "started", "message": f"크롤링 시작됨 ({year_desc}, 목표: {target}건)"}


@router.post("/crawl/stop")
async def stop_crawl():
    """크롤링 중지"""
    global _crawl_state
    proc = _crawl_state.get("process")
    if proc and _crawl_state["is_running"]:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        _crawl_state["is_running"] = False
        _crawl_state["process"] = None
        return {"status": "stopped", "message": "크롤링이 중지되었습니다."}
    return {"status": "not_running", "message": "실행 중인 크롤러가 없습니다."}


@router.get("/crawl/status")
async def get_crawl_status():
    """크롤링 진행 상황 (실시간 대시보드용)"""
    return {
        "is_running": _crawl_state["is_running"],
        "started_at": _crawl_state.get("started_at"),
        "target": _crawl_state.get("target", 0),
        "collected": _crawl_state.get("collected", 0),
        "current_year": _crawl_state.get("current_year"),
        "recent_logs": _crawl_state.get("output_lines", [])[-30:],
        "year_start": _crawl_state.get("year_start"),
        "year_end": _crawl_state.get("year_end"),
        "years_total": _crawl_state.get("years_total", 0),
        "years_completed": _crawl_state.get("years_completed", 0),
        "current_source": _crawl_state.get("current_source"),
        "nyt_collected": _crawl_state.get("nyt_collected", 0),
        "guardian_collected": _crawl_state.get("guardian_collected", 0),
        "dupes_removed": _crawl_state.get("dupes_removed", 0),
        "elapsed_seconds": _crawl_state.get("elapsed_seconds", 0),
        "year_breakdown": _crawl_state.get("year_breakdown", []),
    }


@router.get("/crawl/stats")
async def get_crawl_stats():
    """수집된 뉴스 데이터 통계"""
    db = Database()
    source_stats = await db.get_news_source_stats()
    yearly_stats = await db.get_news_yearly_stats()
    total_count = await db.get_news_articles_count()
    return {
        "total_count": total_count,
        "by_source": source_stats,
        "by_year": yearly_stats,
    }


@router.get("/crawl/year-coverage")
async def get_year_coverage():
    """연도별 수집 커버리지 히트맵 데이터 (2000~현재)"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(text("""
            SELECT
                SUBSTR(published_at, 1, 4) AS year,
                data_source,
                COUNT(*) AS count
            FROM news_articles
            WHERE published_at IS NOT NULL
              AND LENGTH(published_at) >= 4
              AND SUBSTR(published_at, 1, 4) ~ '^\d{4}$'
            GROUP BY SUBSTR(published_at, 1, 4), data_source
            ORDER BY year
        """))
        rows = [dict(r._mapping) for r in result.all()]

    from collections import defaultdict
    coverage = defaultdict(lambda: {"total": 0, "nyt": 0, "guardian": 0, "other": 0})
    for row in rows:
        y = row["year"]
        cnt = row["count"]
        src = row["data_source"]
        coverage[y]["total"] += cnt
        if src == "nyt":
            coverage[y]["nyt"] += cnt
        elif src == "guardian":
            coverage[y]["guardian"] += cnt
        else:
            coverage[y]["other"] += cnt

    current_year = datetime.now().year
    result_list = []
    for yr in range(2000, current_year + 1):
        y_str = str(yr)
        data = coverage.get(y_str, {"total": 0, "nyt": 0, "guardian": 0, "other": 0})
        result_list.append({"year": yr, **data})

    return result_list


@router.get("/crawl/articles/search")
async def search_crawl_articles(
    year: int | None = Query(None),
    source: str | None = Query(None, description="nyt, guardian 등"),
    keyword: str | None = Query(None),
    cls_status: str | None = Query(None, description="all, classified, unclassified, error"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """수집된 기사 검색 (데이터 관리 허브용)"""
    session_factory = get_session_factory()
    from app.models.news_article import NewsArticle as NA

    async with session_factory() as session:
        base = select(NA)
        count_base = select(func.count(NA.id))

        conditions = []
        if year:
            conditions.append(NA.published_at.startswith(str(year)))
        if source:
            conditions.append(NA.data_source == source)
        if keyword:
            kw = f"%{keyword}%"
            conditions.append((NA.title.ilike(kw)) | (NA.description.ilike(kw)))
        if cls_status == "classified":
            conditions.append(NA.is_classified == 1)
        elif cls_status == "unclassified":
            conditions.append(NA.is_classified == 0)
        elif cls_status == "error":
            conditions.append(NA.is_classified == -1)

        for cond in conditions:
            base = base.where(cond)
            count_base = count_base.where(cond)

        total_result = await session.execute(count_base)
        total = total_result.scalar() or 0

        stmt = base.order_by(NA.published_at.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        articles = result.scalars().all()

        items = []
        for a in articles:
            cls_result = a.classification_result or {}
            items.append({
                "id": a.id,
                "title": a.title,
                "description": (a.description or "")[:200],
                "source_name": a.source_name,
                "data_source": a.data_source,
                "url": a.url,
                "published_at": a.published_at,
                "collected_at": a.collected_at,
                "is_classified": a.is_classified,
                "ai_category": cls_result.get("category") if isinstance(cls_result, dict) else None,
                "ai_impact_score": cls_result.get("impact_score") if isinstance(cls_result, dict) else None,
                "ai_is_relevant": cls_result.get("is_relevant") if isinstance(cls_result, dict) else None,
            })

        return {"total": total, "items": items}


class CrawlArticleIdsRequest(BaseModel):
    article_ids: list[str]


@router.delete("/crawl/articles/delete")
async def delete_crawl_articles(req: CrawlArticleIdsRequest):
    """선택한 기사 삭제"""
    if not req.article_ids:
        raise HTTPException(400, "삭제할 기사 ID가 없습니다.")

    session_factory = get_session_factory()
    from app.models.news_article import NewsArticle as NA

    deleted = 0
    async with session_factory() as session:
        result = await session.execute(
            select(NA).where(NA.id.in_(req.article_ids))
        )
        articles = result.scalars().all()
        for a in articles:
            await session.delete(a)
            deleted += 1
        await session.commit()

    return {"deleted": deleted, "ids": req.article_ids}


@router.post("/crawl/articles/recrawl")
async def recrawl_articles(req: CrawlArticleIdsRequest):
    """선택한 기사 재수집 (기존 삭제 후 재크롤링 안내)"""
    if not req.article_ids:
        raise HTTPException(400, "재수집할 기사 ID가 없습니다.")

    session_factory = get_session_factory()
    from app.models.news_article import NewsArticle as NA

    years = set()
    async with session_factory() as session:
        result = await session.execute(
            select(NA.published_at).where(NA.id.in_(req.article_ids))
        )
        for row in result.all():
            if row[0] and len(row[0]) >= 4:
                try:
                    years.add(int(row[0][:4]))
                except ValueError:
                    pass

        for article_id in req.article_ids:
            article = await session.get(NA, article_id)
            if article:
                await session.delete(article)
        await session.commit()

    if not years:
        return {"status": "no_years", "message": "재수집 대상 연도를 파악할 수 없습니다."}

    year_min = min(years)
    year_max = max(years)

    return {
        "status": "deleted",
        "deleted_count": len(req.article_ids),
        "target_years": sorted(years),
        "message": f"{len(req.article_ids)}건 삭제 완료. {year_min}~{year_max}년 재수집을 시작하려면 수동 크롤링에서 해당 범위를 설정하세요.",
    }


# ──────────────────────────────────────────────
# Pipeline Statistics (크롤링 & 학습 관리)
# ──────────────────────────────────────────────

@router.get("/pipeline/classification-stats")
async def get_classification_stats():
    """뉴스 AI 분류 현황 통계"""
    from sqlalchemy import case
    db = Database()
    session_factory = get_session_factory()
    from app.models.news_article import NewsArticle as NA

    async with session_factory() as session:
        # 1. 전체 / 분류완료 / 미분류 / 실패 건수
        result = await session.execute(
            select(
                func.count(NA.id).label("total"),
                func.sum(case((NA.is_classified == 1, 1), else_=0)).label("classified"),
                func.sum(case((NA.is_classified == 0, 1), else_=0)).label("unclassified"),
                func.sum(case((NA.is_classified == -1, 1), else_=0)).label("failed"),
            )
        )
        row = result.one()
        total = row.total or 0
        classified = row.classified or 0
        unclassified = row.unclassified or 0
        failed = row.failed or 0

        # 2. 카테고리별 분류 분포 (classification_result->'category')
        cat_result = await session.execute(text("""
            SELECT 
                classification_result->>'category' AS category,
                COUNT(*) AS count,
                ROUND(AVG((classification_result->>'impact_score')::numeric), 2) AS avg_impact_score
            FROM news_articles
            WHERE is_classified = 1 AND classification_result IS NOT NULL
            GROUP BY classification_result->>'category'
            ORDER BY count DESC
        """))
        category_distribution = [dict(r._mapping) for r in cat_result.all()]

        # 3. 관련성 분포 (is_relevant)
        rel_result = await session.execute(text("""
            SELECT 
                CASE 
                    WHEN (classification_result->>'is_relevant')::text = 'true' THEN 'relevant'
                    ELSE 'irrelevant'
                END AS relevance,
                COUNT(*) AS count
            FROM news_articles
            WHERE is_classified = 1 AND classification_result IS NOT NULL
            GROUP BY 
                CASE 
                    WHEN (classification_result->>'is_relevant')::text = 'true' THEN 'relevant'
                    ELSE 'irrelevant'
                END
        """))
        relevance_distribution = [dict(r._mapping) for r in rel_result.all()]

        # 4. 일별 수집/분류 추이 (최근 30일)
        daily_result = await session.execute(text("""
            SELECT 
                SUBSTR(collected_at, 1, 10) AS date,
                COUNT(*) AS collected,
                SUM(CASE WHEN is_classified = 1 THEN 1 ELSE 0 END) AS classified
            FROM news_articles
            WHERE collected_at >= (CURRENT_DATE - INTERVAL '30 days')::text
            GROUP BY SUBSTR(collected_at, 1, 10)
            ORDER BY date
        """))
        daily_pipeline = [dict(r._mapping) for r in daily_result.all()]

        # 5. 소스별 분류율
        source_cls_result = await session.execute(text("""
            SELECT 
                data_source,
                COUNT(*) AS total,
                SUM(CASE WHEN is_classified = 1 THEN 1 ELSE 0 END) AS classified,
                ROUND(SUM(CASE WHEN is_classified = 1 THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0)::numeric, 1) AS classification_rate
            FROM news_articles
            GROUP BY data_source
            ORDER BY total DESC
        """))
        source_classification = [dict(r._mapping) for r in source_cls_result.all()]

    return {
        "total": total,
        "classified": classified,
        "unclassified": unclassified,
        "failed": failed,
        "classification_rate": round(classified / max(total, 1) * 100, 1),
        "category_distribution": category_distribution,
        "relevance_distribution": relevance_distribution,
        "daily_pipeline": daily_pipeline,
        "source_classification": source_classification,
    }


@router.get("/pipeline/briefing-stats")
async def get_briefing_stats():
    """브리핑 생성 이력 통계"""
    import json
    from pathlib import Path
    from pydantic import ValidationError

    briefing_dir = Path(os.path.dirname(__file__)) / ".." / ".." / "data" / "processed" / "briefings"
    briefings = []

    if briefing_dir.exists():
        for f in sorted(briefing_dir.glob("*.json"), reverse=True)[:30]:
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                    briefings.append({
                        "date": data.get("date", f.stem),
                        "has_news": data.get("has_news", True),
                        "key_factors_count": len(data.get("key_factors", [])),
                        "risk_scenarios_count": len(data.get("risk_scenarios", [])),
                        "crude_assessments_count": len(data.get("crude_assessments", data.get("crude_outlooks", []))),
                        "generated_at": data.get("generated_at", ""),
                        "summary_length": len(data.get("summary", "")),
                    })
            except (json.JSONDecodeError, ValidationError):
                continue

    return {
        "total_briefings": len(briefings),
        "recent": briefings[:10],
    }


@router.get("/pipeline/queue")
async def get_pipeline_queue():
    """분류 대기 중이거나 실패한 기사 큐 조회"""
    db = Database()
    session_factory = get_session_factory()
    from app.models.news_article import NewsArticle as NA

    async with session_factory() as session:
        result = await session.execute(
            select(NA.id, NA.title, NA.published_at, NA.is_classified, NA.classification_error, NA.retry_count)
            .where(NA.is_classified.in_([0, -1]))
            .order_by(NA.published_at.desc())
            .limit(100)
        )
        return [dict(r._mapping) for r in result.all()]

from pydantic import BaseModel
import uuid
import time

class PipelineRetryRequest(BaseModel):
    article_ids: list[str]

@router.post("/pipeline/retry")
async def retry_classification(req: PipelineRetryRequest, background_tasks: BackgroundTasks):
    """지정된 기사들의 재분류를 백그라운드에서 실행하고 작업 이력을 기록"""
    from app.services.news_classifier import NewsClassifier
    from app.models.pipeline_job import PipelineJob

    # 1. 작업 로그 레코드 생성 (상태: queued)
    job_id = f"retry-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    session_factory = get_session_factory()

    async with session_factory() as session:
        job = PipelineJob(
            id=job_id,
            job_type="retry",
            status="queued",
            total_articles=len(req.article_ids),
            article_ids=req.article_ids,
            created_at=now_iso,
        )
        session.add(job)
        await session.commit()

    # 2. 백그라운드 작업 정의
    async def process_retry(ids, jid):
        from app.models.news_article import NewsArticle as NA
        from app.models.pipeline_job import PipelineJob as PJ
        from sqlalchemy import update as sql_update

        sf = get_session_factory()
        t_start = time.time()
        started_iso = datetime.now(timezone.utc).isoformat()

        # 작업 상태 → running
        async with sf() as s:
            await s.execute(sql_update(PJ).where(PJ.id == jid).values(status="running", started_at=started_iso))
            await s.commit()

        success_ids = []
        fail_details = []
        skip_ids = []

        try:
            # 기사 조회
            async with sf() as s:
                result = await s.execute(select(NA).where(NA.id.in_(ids)))
                articles = result.scalars().all()

                # 기존 상태 기록 (before snapshot)
                before_snapshot = {
                    a.id: {
                        "title": a.title[:80] if a.title else "",
                        "is_classified": a.is_classified,
                        "retry_count": a.retry_count or 0,
                        "had_error": a.classification_error is not None,
                    }
                    for a in articles
                }

                # retry count 증가
                for a in articles:
                    a.retry_count = (a.retry_count or 0) + 1
                await s.commit()

                article_dicts = [
                    {
                        "id": a.id, "title": a.title, "description": a.description,
                        "source": a.source_name, "url": a.url, "published_at": a.published_at,
                        "content_snippet": a.content_snippet, "data_source": a.data_source
                    } for a in articles
                ]

            if not article_dicts:
                # 대상 기사 없음
                async with sf() as s:
                    await s.execute(sql_update(PJ).where(PJ.id == jid).values(
                        status="completed",
                        completed_at=datetime.now(timezone.utc).isoformat(),
                        duration_ms=int((time.time() - t_start) * 1000),
                        error_message="No matching articles found in DB",
                    ))
                    await s.commit()
                return

            # AI 분류 실행
            classifier = NewsClassifier()
            await classifier.classify_batch(article_dicts)

            # 분류 후 상태 확인 (after snapshot)
            async with sf() as s:
                result = await s.execute(select(NA).where(NA.id.in_(ids)))
                after_articles = result.scalars().all()

                for a in after_articles:
                    before = before_snapshot.get(a.id, {})
                    if a.is_classified == 1:
                        success_ids.append(a.id)
                    elif a.is_classified == -1:
                        fail_details.append({
                            "id": a.id,
                            "title": (a.title or "")[:80],
                            "error": (a.classification_error or "Unknown error")[:200],
                        })
                    else:
                        skip_ids.append(a.id)

            elapsed_ms = int((time.time() - t_start) * 1000)

            # 최종 상태 기록
            final_status = "completed" if not fail_details else ("completed" if success_ids else "failed")
            async with sf() as s:
                await s.execute(sql_update(PJ).where(PJ.id == jid).values(
                    status=final_status,
                    success_count=len(success_ids),
                    fail_count=len(fail_details),
                    skip_count=len(skip_ids),
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    duration_ms=elapsed_ms,
                    results_detail={
                        "success_ids": success_ids,
                        "failed": fail_details,
                        "skip_ids": skip_ids,
                        "before_snapshot": before_snapshot,
                    },
                ))
                await s.commit()

        except Exception as e:
            elapsed_ms = int((time.time() - t_start) * 1000)
            async with sf() as s:
                await s.execute(sql_update(PJ).where(PJ.id == jid).values(
                    status="failed",
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    duration_ms=elapsed_ms,
                    error_message=str(e)[:500],
                ))
                await s.commit()

    background_tasks.add_task(process_retry, req.article_ids, job_id)
    return {"message": f"Started retry for {len(req.article_ids)} articles", "job_id": job_id}


@router.get("/pipeline/jobs")
async def get_pipeline_jobs(limit: int = 20):
    """파이프라인 작업 이력 조회"""
    from app.models.pipeline_job import PipelineJob as PJ

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(PJ).order_by(PJ.created_at.desc()).limit(limit)
        )
        jobs = result.scalars().all()
        return [
            {
                "id": j.id,
                "job_type": j.job_type,
                "status": j.status,
                "total_articles": j.total_articles,
                "success_count": j.success_count,
                "fail_count": j.fail_count,
                "skip_count": j.skip_count,
                "error_message": j.error_message,
                "results_detail": j.results_detail,
                "created_at": j.created_at,
                "started_at": j.started_at,
                "completed_at": j.completed_at,
                "duration_ms": j.duration_ms,
            }
            for j in jobs
        ]

class OverrideRequest(BaseModel):
    article_id: str
    category: str
    impact_score: float

@router.put("/pipeline/override")
async def override_classification(req: OverrideRequest):
    """기존 분류 결과를 수동으로 오버라이드"""
    session_factory = get_session_factory()
    from app.models.news_article import NewsArticle as NA
    import copy
    
    async with session_factory() as session:
        result = await session.execute(select(NA).where(NA.id == req.article_id))
        article = result.scalar_one_or_none()
        
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
            
        if not article.classification_result:
            raise HTTPException(status_code=400, detail="Cannot override unclassified article")
            
        # Copy and update result
        new_result = copy.deepcopy(article.classification_result)
        new_result["category"] = req.category
        new_result["impact_score"] = req.impact_score
        
        # Save
        article.classification_result = new_result
        await session.commit()
        
    return {"message": "Classification overridden successfully"}


@router.get("/pipeline/articles")
async def get_pipeline_articles(
    status: str = "all",  # all, classified, pending, failed
    limit: int = 50,
    offset: int = 0,
):
    """통합 기사 관리: 원본 데이터 + AI 분석 결과를 함께 반환"""
    session_factory = get_session_factory()
    from app.models.news_article import NewsArticle as NA

    async with session_factory() as session:
        query = select(NA)
        if status == "classified":
            query = query.where(NA.is_classified == 1)
        elif status == "pending":
            query = query.where(NA.is_classified == 0)
        elif status == "failed":
            query = query.where(NA.is_classified == -1)

        query = query.order_by(NA.published_at.desc()).offset(offset).limit(limit)
        result = await session.execute(query)
        articles = result.scalars().all()

        # Count totals for pagination
        count_result = await session.execute(select(func.count(NA.id)))
        total = count_result.scalar() or 0

        items = []
        for a in articles:
            cr = a.classification_result or {}
            impact = cr.get("impact_by_crude", {})
            items.append({
                # ── 원본 데이터 (Input) ──
                "id": a.id,
                "title": a.title,
                "description": (a.description or "")[:200],
                "source_name": a.source_name,
                "data_source": a.data_source,
                "url": a.url,
                "published_at": a.published_at,
                "collected_at": a.collected_at,
                # ── 상태 ──
                "is_classified": a.is_classified,
                "classification_error": a.classification_error,
                "retry_count": a.retry_count or 0,
                "hold_status": a.hold_status or 0,
                # ── AI 분석 결과 (Output) ──
                "ai_category": cr.get("category"),
                "ai_is_relevant": cr.get("is_relevant"),
                "ai_impact_score": cr.get("impact_score"),
                "ai_confidence": cr.get("confidence"),
                "ai_summary": (cr.get("impact_summary") or "")[:300],
                "ai_sub_categories": cr.get("sub_categories", []),
                "ai_translated_title": cr.get("translated_title"),
                "ai_classified_at": cr.get("classified_at"),
                "ai_wti": impact.get("wti", {}).get("score"),
                "ai_brent": impact.get("brent", {}).get("score"),
                "ai_dubai": impact.get("dubai", {}).get("score"),
            })

        return {"total": total, "items": items}


class DeleteArticlesRequest(BaseModel):
    article_ids: list[str]

@router.delete("/pipeline/articles")
async def delete_articles(req: DeleteArticlesRequest):
    """선택한 기사를 DB에서 삭제"""
    from sqlalchemy import delete as sql_delete
    from app.models.news_article import NewsArticle as NA

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            sql_delete(NA).where(NA.id.in_(req.article_ids))
        )
        await session.commit()
        return {"deleted": result.rowcount}

# ──────────────────────────────────────────────
# Crawl Center (크롤링 관리)
# ──────────────────────────────────────────────

@router.put("/scheduler/config")
async def update_scheduler_config(interval_hours: int = 6):
    """스케줄 간격 변경"""
    scheduler = CollectionScheduler()
    return scheduler.update_interval(hours=interval_hours)

@router.post("/scheduler/trigger-news")
async def trigger_news_crawl(background_tasks: BackgroundTasks):
    """뉴스 수동 즉시 트리거"""
    scheduler = CollectionScheduler()
    # 비동기로 백그라운드 실행을 위해 BackgroundTasks 사용
    background_tasks.add_task(scheduler.trigger_manual, "news")
    return {"status": "success", "message": "뉴스 수집이 백그라운드 큐에 등록되었습니다. 1~2분 후 크롤링 이력을 확인하세요."}

@router.get("/crawl/history")
async def get_crawl_history(limit: int = 50, date: str = Query(None, description="YYYY-MM-DD")):
    """크롤링 이력 타임라인"""
    db = Database()
    await db.connect()
    try:
        return await db.get_crawl_history(limit, target_date=date)
    finally:
        await db.close()

@router.get("/crawl/articles/by-date")
async def get_crawl_articles_by_date(date: str = Query(..., description="YYYY-MM-DD")):
    """특정 일자(YYYY-MM-DD) 전체 수집 기사 상세 조회"""
    db = Database()
    await db.connect()
    try:
        return await db.get_articles_by_collected_date(date)
    finally:
        await db.close()

@router.get("/crawl/history/{log_id}/articles")
async def get_crawl_log_articles(log_id: int):
    """특정 크롤링 로그의 수집 기사 상세 조회"""
    db = Database()
    await db.connect()
    try:
        return await db.get_articles_by_crawl_log(log_id)
    finally:
        await db.close()

@router.get("/crawl/source-health")
async def get_source_health():
    """소스별 건강도 모니터링"""
    db = Database()
    await db.connect()
    try:
        return await db.get_source_health()
    finally:
        await db.close()

@router.get("/news/integrity")
async def get_news_integrity():
    """데이터 완결성 검증 리포트"""
    db = Database()
    await db.connect()
    try:
        return await db.get_news_integrity_report()
    finally:
        await db.close()

class HoldRequest(BaseModel):
    ids: list[str]
    hold_status: int

@router.post("/news/hold")
async def hold_articles(req: HoldRequest):
    """기사 보류 상태 변경"""
    db = Database()
    await db.connect()
    try:
        count = await db.update_news_hold_status(req.ids, req.hold_status)
        return {"status": "success", "updated_count": count}
    finally:
        await db.close()

@router.post("/news/manual-insert")
async def manual_insert_article(data: dict):
    """기사 수동 입력"""
    db = Database()
    await db.connect()
    try:
        article_id = await db.manual_insert_article(data)
        return {"status": "success", "id": article_id}
    finally:
        await db.close()

class RetryRequest(BaseModel):
    ids: list[str]

@router.post("/news/retry-integrity")
async def retry_integrity(req: RetryRequest):
    """문제 기사 재수집 (수동 트리거)"""
    # 현재는 단순히 hold 상태를 풀거나, 로직이 필요하지만
    # 일단은 endpoint만 열어둠
    return {"status": "success", "message": "재수집이 스케줄 큐에 등록되었습니다. (mock)"}
