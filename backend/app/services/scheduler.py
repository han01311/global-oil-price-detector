from __future__ import annotations

"""
데이터 수집 자동화 스케줄러
APScheduler를 사용하여 백그라운드에서 주기적으로 데이터를 수집한다.
"""
import asyncio
import logging
from datetime import datetime, date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.database import Database

logger = logging.getLogger(__name__)


async def _log_collection(source: str, task_type: str, func, *args, **kwargs):
    """수집 작업을 실행하고 결과를 collection_logs에 기록한다."""
    db = Database()
    started_at = datetime.utcnow()
    log_entry = {
        "source": source,
        "task_type": task_type,
        "status": "running",
        "records_count": 0,
        "error_message": None,
        "started_at": started_at.isoformat(),
        "completed_at": None,
        "duration_ms": None,
    }

    try:
        result = await func(*args, **kwargs)
        completed_at = datetime.utcnow()
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)

        # 결과에서 레코드 수 추출
        records_count = 0
        if hasattr(result, '__len__'):
            records_count = len(result)
        elif hasattr(result, 'prices'):
            records_count = len(result.prices)
        elif hasattr(result, 'indicators'):
            records_count = len(result.indicators)

        log_entry.update({
            "status": "success",
            "records_count": records_count,
            "completed_at": completed_at.isoformat(),
            "duration_ms": duration_ms,
        })
        logger.info(f"[Scheduler] {source}/{task_type}: 성공 ({records_count}건, {duration_ms}ms)")

    except Exception as e:
        completed_at = datetime.utcnow()
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        error_msg = str(e)[:500]

        # Rate limit 감지
        status = "error"
        if "rate" in error_msg.lower() or "429" in error_msg:
            status = "rate_limited"

        log_entry.update({
            "status": status,
            "error_message": error_msg,
            "completed_at": completed_at.isoformat(),
            "duration_ms": duration_ms,
        })
        logger.error(f"[Scheduler] {source}/{task_type}: {status} — {error_msg}")

    await db.insert_collection_log(log_entry)


async def collect_opinet_prices():
    """Opinet 유가 수집 (Dubai, Brent, WTI)"""
    from app.services.data_collector import DataCollector
    collector = DataCollector()
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    await _log_collection(
        "opinet", "prices",
        collector.collect_prices,
        start_date.isoformat(), end_date.isoformat()
    )


async def collect_eia_inventory():
    """EIA 재고 수집"""
    from app.services.data_collector import DataCollector
    collector = DataCollector()
    end_date = date.today()
    start_date = end_date - timedelta(days=90)
    await _log_collection(
        "eia", "inventory",
        collector.collect_inventory,
        start_date.isoformat(), end_date.isoformat()
    )


async def collect_eia_production():
    """EIA 생산량 수집"""
    from app.services.data_collector import DataCollector
    collector = DataCollector()
    end_date = date.today()
    start_date = end_date - timedelta(days=90)
    await _log_collection(
        "eia", "production",
        collector.collect_production,
        start_date.isoformat(), end_date.isoformat()
    )


async def collect_fred_macro():
    """FRED 거시경제 지표 수집"""
    from app.services.data_collector import DataCollector
    collector = DataCollector()
    end_date = date.today()
    start_date = end_date - timedelta(days=90)
    await _log_collection(
        "fred", "macro",
        collector.collect_macro_data,
        start_date.isoformat(), end_date.isoformat()
    )


async def collect_all_news():
    """뉴스 수집 (NewsAPI + GNews + GDELT)"""
    from app.services.data_collector import DataCollector
    collector = DataCollector()
    await _log_collection(
        "news", "news",
        collector.collect_news,
    )


class CollectionScheduler:
    """데이터 수집 자동화 스케줄러"""

    _instance: "CollectionScheduler | None" = None
    _scheduler: AsyncIOScheduler | None = None
    _is_running: bool = False

    def __new__(cls) -> "CollectionScheduler":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def is_running(self) -> bool:
        return self._is_running

    async def start(self):
        """스케줄러 시작"""
        if self._is_running:
            logger.warning("[Scheduler] Already running.")
            return

        # DB 초기화
        db = Database()
        await db.connect()

        interval_hours = settings.COLLECTION_INTERVAL_HOURS
        self._scheduler = AsyncIOScheduler()

        # Opinet 수집 (유가) — 매 interval 시간마다
        self._scheduler.add_job(
            collect_opinet_prices,
            IntervalTrigger(hours=interval_hours),
            id="opinet_prices",
            name="Opinet 유가 수집",
            replace_existing=True,
        )
        self._scheduler.add_job(
            collect_eia_inventory,
            IntervalTrigger(hours=interval_hours),
            id="eia_inventory",
            name="EIA 재고 수집",
            replace_existing=True,
        )
        self._scheduler.add_job(
            collect_eia_production,
            IntervalTrigger(hours=interval_hours),
            id="eia_production",
            name="EIA 생산량 수집",
            replace_existing=True,
        )

        # FRED 수집 — 12시간마다 (거시경제 데이터는 자주 변하지 않음)
        self._scheduler.add_job(
            collect_fred_macro,
            IntervalTrigger(hours=max(interval_hours, 12)),
            id="fred_macro",
            name="FRED 거시경제 수집",
            replace_existing=True,
        )

        # 뉴스 수집 — 매 interval 시간마다
        self._scheduler.add_job(
            collect_all_news,
            IntervalTrigger(hours=interval_hours),
            id="news_collect",
            name="뉴스 수집 (NewsAPI + GNews + GDELT)",
            replace_existing=True,
        )

        self._scheduler.start()
        self._is_running = True
        logger.info(f"[Scheduler] 시작됨 (수집 주기: {interval_hours}시간)")

    async def stop(self):
        """스케줄러 정지"""
        if self._scheduler and self._is_running:
            self._scheduler.shutdown(wait=False)
            self._is_running = False
            logger.info("[Scheduler] 정지됨")

    def get_status(self) -> dict:
        """스케줄러 현재 상태"""
        jobs = []
        if self._scheduler:
            for job in self._scheduler.get_jobs():
                next_run = job.next_run_time
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": next_run.isoformat() if next_run else None,
                })

        return {
            "is_running": self._is_running,
            "interval_hours": settings.COLLECTION_INTERVAL_HOURS,
            "jobs": jobs,
        }

    async def trigger_manual(self, source: str) -> dict:
        """수동으로 특정 소스 수집을 트리거한다."""
        job_map = {
            "opinet_prices": collect_opinet_prices,
            "eia_inventory": collect_eia_inventory,
            "eia_production": collect_eia_production,
            "fred_macro": collect_fred_macro,
            "news": collect_all_news,
        }

        func = job_map.get(source)
        if not func:
            return {"status": "error", "message": f"Unknown source: {source}. Available: {list(job_map.keys())}"}

        try:
            await func()
            return {"status": "success", "message": f"{source} collection triggered successfully."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
