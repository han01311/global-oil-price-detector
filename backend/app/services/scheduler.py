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
    return result if 'result' in locals() else None


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


async def collect_all_news(start_date: str | None = None, end_date: str | None = None):
    """뉴스 수집 (NewsAPI + GNews + GDELT) → AI 분류 → 일일 브리핑 자동 생성"""
    from app.services.data_collector import DataCollector
    from app.services.news_classifier import NewsClassifier
    
    collector = DataCollector()
    articles = await _log_collection(
        "news", "news",
        collector.collect_news,
        start_date=start_date, end_date=end_date
    )
    
    # 수집 완료 후 AI 분류 진행 (await로 완료 대기)
    classified_articles = []
    if articles:
        classifier = NewsClassifier()
        try:
            classified_articles = await classifier.classify_batch(articles)
            logger.info(f"[Scheduler] 뉴스 AI 분류 완료: {len(classified_articles)}건")
        except Exception as e:
            logger.error(f"[Scheduler] 뉴스 AI 분류 실패: {e}")
    
    # 분류된 뉴스가 있으면 일일 브리핑 자동 생성
    if classified_articles:
        asyncio.create_task(_generate_daily_briefing_after_classification(classified_articles))
    else:
        logger.info("[Scheduler] 분류된 뉴스 0건 — 일일 브리핑 생성 스킵")


async def _generate_daily_briefing_after_classification(classified_articles):
    """뉴스 분류 완료 후 자동으로 일일 브리핑을 생성한다."""
    try:
        from app.services.briefing_generator import BriefingGenerator
        from app.api.forecast import _run_forecast_pipeline
        from app.core.database import Database

        logger.info("[Scheduler] 일일 브리핑 자동 생성 시작...")

        # 1. 유종별 당일/전일 가격 데이터 조회
        db = Database()
        price_data = await _fetch_crude_price_data(db)

        # 2. 예측 파이프라인 실행 (key_factors 등에 필요한 forecast 데이터)
        forecast_result, _, _ = await _run_forecast_pipeline()

        # 3. 분류된 기사를 dict로 변환
        articles_as_dicts = []
        for a in classified_articles:
            if hasattr(a, 'model_dump'):
                articles_as_dicts.append(a.model_dump())
            elif isinstance(a, dict):
                articles_as_dicts.append(a)

        # 4. 브리핑 생성 (캐시 강제 갱신)
        generator = BriefingGenerator()
        briefing = await generator.generate_briefing(
            forecast=forecast_result,
            classified_articles=articles_as_dicts,
            price_data=price_data,
            force=True,
        )
        logger.info(f"[Scheduler] 일일 브리핑 자동 생성 완료: {briefing.date}")

    except Exception as e:
        logger.error(f"[Scheduler] 일일 브리핑 자동 생성 실패: {e}")


async def _fetch_crude_price_data(db) -> dict:
    """DB에서 유종별 최근 2일 가격을 조회하여 today/yesterday 딕셔너리로 반환"""
    price_data = {}
    try:
        rows = await db.get_oil_prices(limit=10)
        if not rows:
            return price_data

        # 날짜별로 그룹핑
        dates = sorted(set(r["date"] for r in rows), reverse=True)
        today_date = dates[0] if len(dates) > 0 else None
        yesterday_date = dates[1] if len(dates) > 1 else None

        for crude in ["dubai", "brent", "wti"]:
            today_price = None
            yesterday_price = None

            for r in rows:
                price_field = f"{crude}_price" if f"{crude}_price" in r else crude
                price_val = r.get(price_field) or r.get(crude)
                if price_val and price_val > 0:
                    if r["date"] == today_date and today_price is None:
                        today_price = price_val
                    elif r["date"] == yesterday_date and yesterday_price is None:
                        yesterday_price = price_val

            price_data[crude] = {
                "today": today_price or 0,
                "yesterday": yesterday_price or 0,
            }

        price_data["_data_as_of"] = today_date or ""
        price_data["_prev_date"] = yesterday_date or ""
    except Exception as e:
        logger.error(f"[Scheduler] 유가 데이터 조회 실패: {e}")

    return price_data


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

        # 최신 데이터 누락 여부 점검 후 필요 시 즉시 실행
        run_now = None
        try:
            db_rows = await db.get_oil_prices(limit=1)
            if not db_rows:
                run_now = datetime.now()
                logger.info("[Scheduler] DB에 유가 데이터가 없습니다. 즉시 수집을 시작합니다.")
            else:
                try:
                    latest_date = datetime.strptime(db_rows[0]["date"], "%Y-%m-%d").date()
                    if (date.today() - latest_date).days > 1:
                        run_now = datetime.now()
                        logger.info(f"[Scheduler] 최신 데이터({latest_date})가 지연되었습니다. 즉시 수집을 시작합니다.")
                except Exception as e:
                    logger.error(f"[Scheduler] 최신 데이터 날짜 파싱 오류: {e}")
        except Exception as e:
            logger.error(f"[Scheduler] DB 조회 오류: {e}")
            run_now = datetime.now()

        job_kwargs = {"replace_existing": True}
        if run_now:
            job_kwargs["next_run_time"] = run_now

        # Opinet 수집 (유가) — 매 interval 시간마다
        self._scheduler.add_job(
            collect_opinet_prices,
            IntervalTrigger(hours=interval_hours),
            id="opinet_prices",
            name="Opinet 유가 수집",
            **job_kwargs,
        )
        self._scheduler.add_job(
            collect_eia_inventory,
            IntervalTrigger(hours=interval_hours),
            id="eia_inventory",
            name="EIA 재고 수집",
            **job_kwargs,
        )
        self._scheduler.add_job(
            collect_eia_production,
            IntervalTrigger(hours=interval_hours),
            id="eia_production",
            name="EIA 생산량 수집",
            **job_kwargs,
        )

        # FRED 수집 — 12시간마다 (거시경제 데이터는 자주 변하지 않음)
        self._scheduler.add_job(
            collect_fred_macro,
            IntervalTrigger(hours=max(interval_hours, 12)),
            id="fred_macro",
            name="FRED 거시경제 수집",
            **job_kwargs,
        )

        # 뉴스 수집 — 매 interval 시간마다
        self._scheduler.add_job(
            collect_all_news,
            IntervalTrigger(hours=interval_hours),
            id="news_collect",
            name="뉴스 수집 (NewsAPI + GNews + GDELT)",
            **job_kwargs,
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

    def update_interval(self, hours: int) -> dict:
        """실시간으로 스케줄 간격을 변경한다."""
        if not self._scheduler or not self._is_running:
            return {"status": "error", "message": "Scheduler is not running"}
        if hours < 1 or hours > 24:
            return {"status": "error", "message": "Interval must be 1-24 hours"}

        job_ids = ["opinet_prices", "eia_inventory", "eia_production", "news_collect"]
        for job_id in job_ids:
            try:
                self._scheduler.reschedule_job(
                    job_id,
                    trigger=IntervalTrigger(hours=hours),
                )
            except Exception as e:
                logger.warning(f"[Scheduler] Failed to reschedule {job_id}: {e}")

        # FRED는 최소 12시간
        try:
            self._scheduler.reschedule_job(
                "fred_macro",
                trigger=IntervalTrigger(hours=max(hours, 12)),
            )
        except Exception as e:
            logger.warning(f"[Scheduler] Failed to reschedule fred_macro: {e}")

        logger.info(f"[Scheduler] 간격 변경: {hours}시간")
        return {
            "status": "success",
            "message": f"Interval updated to {hours} hours",
            "interval_hours": hours,
        }

    def get_detailed_status(self) -> dict:
        """각 Job별 상세 상태 (마지막/다음 실행, 최근 성공/실패)"""
        jobs = []
        if self._scheduler:
            for job in self._scheduler.get_jobs():
                next_run = job.next_run_time
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": next_run.isoformat() if next_run else None,
                })

        # 현재 간격 추정 (첫 번째 job의 trigger에서)
        current_interval = settings.COLLECTION_INTERVAL_HOURS
        if self._scheduler:
            try:
                job = self._scheduler.get_job("opinet_prices")
                if job and hasattr(job.trigger, 'interval'):
                    current_interval = int(job.trigger.interval.total_seconds() / 3600)
            except Exception:
                pass

        return {
            "is_running": self._is_running,
            "interval_hours": current_interval,
            "jobs": jobs,
            "job_count": len(jobs),
        }

