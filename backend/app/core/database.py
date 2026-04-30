from __future__ import annotations

"""
PostgreSQL 비동기 데이터베이스 관리 모듈 (SQLAlchemy)
수집된 데이터의 영구 저장 및 관리자 조회를 담당한다.

기존 Database 싱글톤의 공개 인터페이스를 유지하되,
내부 구현을 aiosqlite → SQLAlchemy + asyncpg 로 교체하여
동시성(Concurrency) 문제를 근본적으로 해결한다.
"""
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select, func, text, update, literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.base import get_session_factory, init_db, close_db
from app.models.oil_price import OilPrice as OilPriceModel
from app.models.oil_inventory import OilInventory as OilInventoryModel
from app.models.oil_production import OilProduction as OilProductionModel
from app.models.macro_indicator import MacroIndicator as MacroIndicatorModel
from app.models.news_article import NewsArticle as NewsArticleModel
from app.models.collection_log import CollectionLog as CollectionLogModel
from app.models.rate_limit_counter import RateLimitCounter as RateLimitCounterModel

logger = logging.getLogger(__name__)


def _row_to_dict(row) -> dict:
    """SQLAlchemy ORM 모델 인스턴스를 dict로 변환"""
    return {c.key: getattr(row, c.key) for c in row.__table__.columns}


class Database:
    """비동기 PostgreSQL 데이터베이스 — 싱글톤 (기존 인터페이스 호환)"""

    _instance: "Database | None" = None

    def __new__(cls) -> "Database":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        """DB 연결 및 테이블 초기화 (CREATE IF NOT EXISTS)"""
        await init_db()
        logger.info("PostgreSQL DB initialized (SQLAlchemy)")

    async def close(self) -> None:
        """DB 엔진 종료"""
        await close_db()
        Database._instance = None
        logger.info("PostgreSQL DB engine disposed.")

    # ──────────────────────────────────────────────
    # 유가 데이터 CRUD
    # ──────────────────────────────────────────────

    async def upsert_oil_prices(self, rows: list[dict]) -> int:
        """유가 데이터를 upsert (기존 값 보존, 새 값만 업데이트)"""
        session_factory = get_session_factory()
        now = datetime.utcnow().isoformat()
        count = 0
        async with session_factory() as session:
            for row in rows:
                try:
                    stmt = pg_insert(OilPriceModel).values(
                        date=row["date"],
                        dubai=row.get("dubai"),
                        wti=row.get("wti"),
                        brent=row.get("brent"),
                        source=row.get("source", "opinet"),
                        collected_at=now,
                    )
                    stmt = stmt.on_conflict_do_update(
                        constraint="uq_oil_prices_date_source",
                        set_={
                            "dubai": func.coalesce(stmt.excluded.dubai, OilPriceModel.dubai),
                            "wti": func.coalesce(stmt.excluded.wti, OilPriceModel.wti),
                            "brent": func.coalesce(stmt.excluded.brent, OilPriceModel.brent),
                            "collected_at": stmt.excluded.collected_at,
                        },
                    )
                    await session.execute(stmt)
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to upsert oil_price row {row.get('date')}: {e}")
            await session.commit()
        return count

    async def get_oil_prices(
        self, start_date: str | None = None, end_date: str | None = None,
        limit: int = 500, offset: int = 0
    ) -> list[dict]:
        """유가 데이터 조회"""
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(OilPriceModel)
            if start_date:
                stmt = stmt.where(OilPriceModel.date >= start_date)
            if end_date:
                stmt = stmt.where(OilPriceModel.date <= end_date)
            stmt = stmt.order_by(OilPriceModel.date.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [_row_to_dict(r) for r in result.scalars().all()]

    async def get_oil_prices_count(self) -> int:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(func.count(OilPriceModel.id)))
            return result.scalar_one()

    # ──────────────────────────────────────────────
    # 재고 CRUD
    # ──────────────────────────────────────────────

    async def upsert_oil_inventory(self, rows: list[dict]) -> int:
        session_factory = get_session_factory()
        now = datetime.utcnow().isoformat()
        count = 0
        async with session_factory() as session:
            for row in rows:
                try:
                    stmt = pg_insert(OilInventoryModel).values(
                        date=row["date"],
                        inventory_mbbl=row.get("inventory_mbbl"),
                        collected_at=now,
                    )
                    stmt = stmt.on_conflict_do_update(
                        constraint="uq_oil_inventory_date",
                        set_={
                            "inventory_mbbl": stmt.excluded.inventory_mbbl,
                            "collected_at": stmt.excluded.collected_at,
                        },
                    )
                    await session.execute(stmt)
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to upsert inventory row: {e}")
            await session.commit()
        return count

    async def get_oil_inventory(
        self, start_date: str | None = None, end_date: str | None = None,
        limit: int = 500, offset: int = 0
    ) -> list[dict]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(OilInventoryModel)
            if start_date:
                stmt = stmt.where(OilInventoryModel.date >= start_date)
            if end_date:
                stmt = stmt.where(OilInventoryModel.date <= end_date)
            stmt = stmt.order_by(OilInventoryModel.date.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [_row_to_dict(r) for r in result.scalars().all()]

    async def get_oil_inventory_count(self) -> int:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(func.count(OilInventoryModel.id)))
            return result.scalar_one()

    # ──────────────────────────────────────────────
    # 생산량 CRUD
    # ──────────────────────────────────────────────

    async def upsert_oil_production(self, rows: list[dict]) -> int:
        session_factory = get_session_factory()
        now = datetime.utcnow().isoformat()
        count = 0
        async with session_factory() as session:
            for row in rows:
                try:
                    stmt = pg_insert(OilProductionModel).values(
                        date=row["date"],
                        production_mbbl_d=row.get("production_mbbl_d"),
                        collected_at=now,
                    )
                    stmt = stmt.on_conflict_do_update(
                        constraint="uq_oil_production_date",
                        set_={
                            "production_mbbl_d": stmt.excluded.production_mbbl_d,
                            "collected_at": stmt.excluded.collected_at,
                        },
                    )
                    await session.execute(stmt)
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to upsert production row: {e}")
            await session.commit()
        return count

    async def get_oil_production_count(self) -> int:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(func.count(OilProductionModel.id)))
            return result.scalar_one()

    async def get_oil_production_range(
        self, start_date: str, end_date: str, limit: int = 500
    ) -> list[dict]:
        """생산량 데이터 범위 조회"""
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = (
                select(OilProductionModel)
                .where(OilProductionModel.date >= start_date)
                .where(OilProductionModel.date <= end_date)
                .order_by(OilProductionModel.date.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [_row_to_dict(r) for r in result.scalars().all()]

    async def get_oil_production(
        self, start_date: str | None = None, end_date: str | None = None,
        limit: int = 500, offset: int = 0
    ) -> list[dict]:
        """생산량 데이터 페이지네이션 조회"""
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(OilProductionModel)
            if start_date:
                stmt = stmt.where(OilProductionModel.date >= start_date)
            if end_date:
                stmt = stmt.where(OilProductionModel.date <= end_date)
            stmt = stmt.order_by(OilProductionModel.date.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [_row_to_dict(r) for r in result.scalars().all()]

    async def get_oil_production_count(self, start_date: str | None = None, end_date: str | None = None) -> int:
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(func.count(OilProductionModel.id))
            if start_date:
                stmt = stmt.where(OilProductionModel.date >= start_date)
            if end_date:
                stmt = stmt.where(OilProductionModel.date <= end_date)
            result = await session.execute(stmt)
            return result.scalar_one()

    # ──────────────────────────────────────────────
    # 거시 경제 CRUD
    # ──────────────────────────────────────────────

    async def upsert_macro_indicators(self, rows: list[dict]) -> int:
        session_factory = get_session_factory()
        now = datetime.utcnow().isoformat()
        count = 0
        async with session_factory() as session:
            for row in rows:
                try:
                    stmt = pg_insert(MacroIndicatorModel).values(
                        date=row["date"],
                        fed_rate=row.get("fed_rate"),
                        dollar_index=row.get("dollar_index"),
                        source=row.get("source", "fred"),
                        collected_at=now,
                    )
                    stmt = stmt.on_conflict_do_update(
                        constraint="uq_macro_indicators_date_source",
                        set_={
                            "fed_rate": stmt.excluded.fed_rate,
                            "dollar_index": stmt.excluded.dollar_index,
                            "collected_at": stmt.excluded.collected_at,
                        },
                    )
                    await session.execute(stmt)
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to upsert macro row: {e}")
            await session.commit()
        return count

    async def get_macro_indicators(
        self, start_date: str | None = None, end_date: str | None = None,
        limit: int = 500, offset: int = 0
    ) -> list[dict]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(MacroIndicatorModel)
            if start_date:
                stmt = stmt.where(MacroIndicatorModel.date >= start_date)
            if end_date:
                stmt = stmt.where(MacroIndicatorModel.date <= end_date)
            stmt = stmt.order_by(MacroIndicatorModel.date.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [_row_to_dict(r) for r in result.scalars().all()]

    async def get_macro_indicators_count(self) -> int:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(func.count(MacroIndicatorModel.id)))
            return result.scalar_one()

    # ──────────────────────────────────────────────
    # 뉴스 CRUD
    # ──────────────────────────────────────────────

    async def upsert_news_articles(self, articles: list[dict]) -> int:
        session_factory = get_session_factory()
        now = datetime.utcnow().isoformat()
        count = 0
        async with session_factory() as session:
            for a in articles:
                try:
                    stmt = pg_insert(NewsArticleModel).values(
                        id=a["id"],
                        title=a["title"],
                        description=a.get("description"),
                        source_name=a.get("source"),
                        url=a["url"],
                        published_at=a.get("published_at"),
                        content_snippet=a.get("content_snippet"),
                        data_source=a.get("data_source"),
                        collected_at=now,
                    )
                    stmt = stmt.on_conflict_do_nothing(index_elements=["id"]).returning(NewsArticleModel.id)
                    result = await session.execute(stmt)
                    if result.scalar():
                        count += 1
                        a['_is_new'] = True
                except Exception as e:
                    logger.warning(f"Failed to upsert news article: {e}")
            await session.commit()
        return count

    async def get_news_articles(
        self, data_source: str | None = None,
        classified_only: bool = False,
        limit: int = 50, offset: int = 0
    ) -> list[dict]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(NewsArticleModel)
            if data_source:
                stmt = stmt.where(NewsArticleModel.data_source == data_source)
            if classified_only:
                stmt = stmt.where(NewsArticleModel.is_classified == 1)
            stmt = stmt.order_by(NewsArticleModel.published_at.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [_row_to_dict(r) for r in result.scalars().all()]

    async def get_news_articles_count(self, data_source: str | None = None) -> int:
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(func.count(NewsArticleModel.id))
            if data_source:
                stmt = stmt.where(NewsArticleModel.data_source == data_source)
            result = await session.execute(stmt)
            return result.scalar_one()

    async def get_news_date_counts(self, start_date: str, end_date: str) -> list[dict]:
        """날짜별 기사 건수 반환 (차트 마커용, 경량 쿼리)"""
        session_factory = get_session_factory()
        async with session_factory() as session:
            date_col = func.substr(NewsArticleModel.published_at, 1, 10).label("date")
            stmt = (
                select(
                    date_col,
                    func.count().label("count"),
                    NewsArticleModel.data_source,
                )
                .where(func.substr(NewsArticleModel.published_at, 1, 10).between(start_date, end_date))
                .group_by(date_col, NewsArticleModel.data_source)
                .order_by(date_col)
            )
            result = await session.execute(stmt)
            return [dict(r._mapping) for r in result.all()]

    async def get_news_by_date(self, target_date: str, limit: int = 50) -> list[dict]:
        """특정 날짜의 기사 목록 반환"""
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = (
                select(NewsArticleModel)
                .where(NewsArticleModel.published_at.startswith(target_date))
                .order_by(NewsArticleModel.published_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [_row_to_dict(r) for r in result.scalars().all()]

    async def get_news_by_range(self, start_date: str, end_date: str, limit: int = 200) -> list[dict]:
        """특정 기간의 기사 목록 반환"""
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = (
                select(NewsArticleModel)
                .where(NewsArticleModel.published_at >= start_date)
                .where(NewsArticleModel.published_at <= end_date + "T23:59:59")
                .order_by(NewsArticleModel.published_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [_row_to_dict(r) for r in result.scalars().all()]

    async def get_news_source_stats(self) -> list[dict]:
        """뉴스 기사 소스별 통계"""
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = (
                select(
                    NewsArticleModel.data_source,
                    func.count().label("count"),
                    func.min(NewsArticleModel.published_at).label("oldest_date"),
                    func.max(NewsArticleModel.published_at).label("newest_date"),
                    func.count(func.distinct(NewsArticleModel.source_name)).label("source_count"),
                )
                .group_by(NewsArticleModel.data_source)
                .order_by(func.count().desc())
            )
            result = await session.execute(stmt)
            return [dict(r._mapping) for r in result.all()]

    async def get_historical_price_changes(self, base_date_str: str) -> dict:
        """
        Calculate the percentage price changes for 1d, 7d, 30d relative to the base_date.
        Handles missing days (weekends/holidays) via forward-fill logic.
        Returns a dict like: {'wti_change_1d': 1.5, 'dubai_change_7d': -0.2, ...}
        """
        from datetime import datetime, timedelta
        from sqlalchemy import text
        
        try:
            # Parse ISO 8601 string to YYYY-MM-DD
            base_date = datetime.fromisoformat(base_date_str.replace('Z', '+00:00')).date()
        except ValueError:
            base_date = datetime.strptime(base_date_str[:10], "%Y-%m-%d").date()
            
        target_dates = {
            "1d": base_date + timedelta(days=1),
            "7d": base_date + timedelta(days=7),
            "30d": base_date + timedelta(days=30),
        }
        
        crude_types = ["dubai", "brent", "wti"]
        changes = {f"{c}_change_{p}": None for c in crude_types for p in ["1d", "7d", "30d"]}
        
        session_factory = get_session_factory()
        async with session_factory() as session:
            for crude in crude_types:
                # 1. Get base price (closest trading day ON OR BEFORE base_date)
                stmt_base = text(f"""
                    SELECT {crude} FROM oil_prices 
                    WHERE date <= :b_date AND {crude} IS NOT NULL 
                    ORDER BY date DESC LIMIT 1
                """)
                res_base = await session.execute(stmt_base, {"b_date": base_date.isoformat()})
                base_price_row = res_base.scalar()
                
                if not base_price_row:
                    continue  # No historical data before this date for this crude
                    
                base_price = float(base_price_row)
                if base_price == 0:
                    continue
                    
                # 2. Get future prices for each period
                for period, t_date in target_dates.items():
                    # Closest trading day ON OR AFTER target_date
                    stmt_future = text(f"""
                        SELECT {crude} FROM oil_prices 
                        WHERE date >= :t_date AND {crude} IS NOT NULL 
                        ORDER BY date ASC LIMIT 1
                    """)
                    res_future = await session.execute(stmt_future, {"t_date": t_date.isoformat()})
                    future_price_row = res_future.scalar()
                    
                    if future_price_row:
                        future_price = float(future_price_row)
                        pct_change = ((future_price - base_price) / base_price) * 100.0
                        changes[f"{crude}_change_{period}"] = round(pct_change, 2)
                        
        return changes

    async def get_news_yearly_stats(self) -> list[dict]:
        """뉴스 기사 연도별 통계"""
        session_factory = get_session_factory()
        async with session_factory() as session:
            year_col = func.substr(NewsArticleModel.published_at, 1, 4).label("year")
            stmt = (
                select(
                    year_col,
                    NewsArticleModel.data_source,
                    func.count().label("count"),
                )
                .where(NewsArticleModel.published_at.isnot(None))
                .group_by(year_col, NewsArticleModel.data_source)
                .order_by(year_col)
            )
            result = await session.execute(stmt)
            return [dict(r._mapping) for r in result.all()]

    # ──────────────────────────────────────────────
    # 수집 로그 CRUD
    # ──────────────────────────────────────────────

    async def insert_collection_log(self, log: dict) -> int:
        session_factory = get_session_factory()
        async with session_factory() as session:
            entry = CollectionLogModel(
                source=log["source"],
                task_type=log["task_type"],
                status=log["status"],
                records_count=log.get("records_count", 0),
                error_message=log.get("error_message"),
                started_at=log["started_at"],
                completed_at=log.get("completed_at"),
                duration_ms=log.get("duration_ms"),
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
            return entry.id

    async def get_collection_logs(
        self, source: str | None = None, status: str | None = None,
        limit: int = 50, offset: int = 0
    ) -> list[dict]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(CollectionLogModel)
            if source:
                stmt = stmt.where(CollectionLogModel.source == source)
            if status:
                stmt = stmt.where(CollectionLogModel.status == status)
            stmt = stmt.order_by(CollectionLogModel.id.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [_row_to_dict(r) for r in result.scalars().all()]

    async def get_collection_logs_count(
        self, source: str | None = None, status: str | None = None
    ) -> int:
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(func.count(CollectionLogModel.id))
            if source:
                stmt = stmt.where(CollectionLogModel.source == source)
            if status:
                stmt = stmt.where(CollectionLogModel.status == status)
            result = await session.execute(stmt)
            return result.scalar_one()

    async def get_log_stats_by_source(self) -> list[dict]:
        """소스별 최근 로그 통계"""
        from sqlalchemy import case, Integer as SAInt
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = (
                select(
                    CollectionLogModel.source,
                    func.count().label("total_runs"),
                    func.sum(
                        case(
                            (CollectionLogModel.status == "success", 1),
                            else_=0,
                        )
                    ).label("success_count"),
                    func.sum(
                        case(
                            (CollectionLogModel.status == "error", 1),
                            else_=0,
                        )
                    ).label("error_count"),
                    func.sum(
                        case(
                            (CollectionLogModel.status == "rate_limited", 1),
                            else_=0,
                        )
                    ).label("rate_limited_count"),
                    func.max(CollectionLogModel.completed_at).label("last_run_at"),
                    func.sum(CollectionLogModel.records_count).label("total_records"),
                )
                .group_by(CollectionLogModel.source)
                .order_by(CollectionLogModel.source)
            )
            result = await session.execute(stmt)
            return [dict(r._mapping) for r in result.all()]

    # ──────────────────────────────────────────────
    # Rate Limit 카운터 CRUD
    # ──────────────────────────────────────────────

    async def increment_rate_counter(self, source: str) -> int:
        """Rate limit 카운터 증가, 현재 카운트 반환"""
        session_factory = get_session_factory()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        now = datetime.utcnow().isoformat()
        async with session_factory() as session:
            stmt = pg_insert(RateLimitCounterModel).values(
                source=source, date=today, request_count=1, last_request_at=now
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_rate_limit_source_date",
                set_={
                    "request_count": RateLimitCounterModel.request_count + 1,
                    "last_request_at": now,
                },
            )
            await session.execute(stmt)
            await session.commit()

            result = await session.execute(
                select(RateLimitCounterModel.request_count)
                .where(RateLimitCounterModel.source == source)
                .where(RateLimitCounterModel.date == today)
            )
            return result.scalar_one()

    async def get_rate_counter(self, source: str) -> dict:
        """현재 일일 Rate limit 카운터 조회"""
        session_factory = get_session_factory()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        async with session_factory() as session:
            result = await session.execute(
                select(RateLimitCounterModel)
                .where(RateLimitCounterModel.source == source)
                .where(RateLimitCounterModel.date == today)
            )
            row = result.scalar_one_or_none()
            if row:
                return {
                    "source": source, "date": today,
                    "request_count": row.request_count,
                    "last_request_at": row.last_request_at,
                }
            return {"source": source, "date": today, "request_count": 0, "last_request_at": None}

    async def get_all_rate_counters(self) -> list[dict]:
        """모든 소스의 오늘 Rate limit 카운터"""
        session_factory = get_session_factory()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        async with session_factory() as session:
            result = await session.execute(
                select(RateLimitCounterModel)
                .where(RateLimitCounterModel.date == today)
            )
            rows = result.scalars().all()
            return [
                {
                    "source": r.source, "date": today,
                    "request_count": r.request_count,
                    "last_request_at": r.last_request_at,
                }
                for r in rows
            ]

    # ──────────────────────────────────────────────
    # Overview 통계
    # ──────────────────────────────────────────────

    async def get_overview(self) -> dict:
        """전체 DB 현황 통계"""
        session_factory = get_session_factory()
        models_config = {
            "oil_prices": (OilPriceModel, OilPriceModel.collected_at),
            "oil_inventory": (OilInventoryModel, OilInventoryModel.collected_at),
            "oil_production": (OilProductionModel, OilProductionModel.collected_at),
            "macro_indicators": (MacroIndicatorModel, MacroIndicatorModel.collected_at),
            "news_articles": (NewsArticleModel, NewsArticleModel.collected_at),
            "collection_logs": (CollectionLogModel, CollectionLogModel.completed_at),
        }
        overview = {}
        async with session_factory() as session:
            for table_name, (model, date_col) in models_config.items():
                result = await session.execute(
                    select(func.count(model.id), func.max(date_col))
                )
                row = result.one()
                overview[table_name] = {
                    "count": row[0] or 0,
                    "last_collected": row[1],
                }
        return overview

    # ──────────────────────────────────────────────
    # 크롤링 관리 (Crawl Center)
    # ──────────────────────────────────────────────

    async def get_crawl_history(self, limit: int = 50, target_date: str = None) -> list[dict]:
        """최근 크롤링 이력 타임라인. target_date가 있으면 해당 일자(YYYY-MM-DD)만 필터링."""
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(CollectionLogModel)
            
            if target_date:
                # started_at이 해당 일자로 시작하는 것들만 필터링
                stmt = stmt.where(CollectionLogModel.started_at.startswith(target_date))
                
            stmt = stmt.order_by(CollectionLogModel.id.desc()).limit(limit)
            result = await session.execute(stmt)
            return [_row_to_dict(r) for r in result.scalars().all()]

    async def get_articles_by_collected_date(self, target_date: str) -> list[dict]:
        """특정 일자(YYYY-MM-DD)에 DB에 인서트된(collected_at) 모든 기사 목록 조회"""
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = (
                select(NewsArticleModel)
                .where(NewsArticleModel.collected_at.startswith(target_date))
                .order_by(NewsArticleModel.published_at.desc())
            )
            result = await session.execute(stmt)
            articles = result.scalars().all()
            
            res = []
            for a in articles:
                d = _row_to_dict(a)
                issue = "none"
                if not a.description:
                    issue = "no_desc"
                elif a.is_classified == 1 and not a.classification_result:
                    issue = "cls_broken"
                d["issue_type"] = issue
                res.append(d)
                
            return res

    async def get_articles_by_crawl_log(self, log_id: int) -> list[dict]:
        """특정 크롤링 로그(작업)에서 수집된 기사 목록 상세 조회"""
        session_factory = get_session_factory()
        async with session_factory() as session:
            # 1. 로그 정보 가져오기
            log = await session.get(CollectionLogModel, log_id)
            if not log or not log.started_at or not log.completed_at:
                return []
                
            # 2. 해당 시간대에 수집된 기사 목록 가져오기
            stmt = (
                select(NewsArticleModel)
                .where(NewsArticleModel.collected_at >= log.started_at)
                .where(NewsArticleModel.collected_at <= log.completed_at)
                .order_by(NewsArticleModel.published_at.desc())
            )
            result = await session.execute(stmt)
            articles = result.scalars().all()
            
            # 3. 반환용으로 변환하면서 issue_type 추가
            res = []
            for a in articles:
                d = _row_to_dict(a)
                issue = "none"
                if not a.description:
                    issue = "no_desc"
                elif a.is_classified == 1 and not a.classification_result:
                    issue = "cls_broken"
                d["issue_type"] = issue
                res.append(d)
                
            return res

    async def get_source_health(self) -> list[dict]:
        """소스별 건강도 — 최신 기사 날짜, 마지막 수집, 평균 응답시간, 에러율"""
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(text("""
                WITH source_freshness AS (
                    SELECT data_source,
                        COUNT(*) AS article_count,
                        MAX(published_at) AS newest_article,
                        MAX(collected_at) AS last_crawled
                    FROM news_articles
                    GROUP BY data_source
                    
                    UNION ALL
                    
                    SELECT source AS data_source,
                        COUNT(*) AS article_count,
                        MAX(date) AS newest_article,
                        MAX(collected_at) AS last_crawled
                    FROM oil_prices
                    GROUP BY source
                    
                    UNION ALL
                    
                    SELECT 'eia_inventory' AS data_source,
                        COUNT(*) AS article_count,
                        MAX(date) AS newest_article,
                        MAX(collected_at) AS last_crawled
                    FROM oil_inventory
                    
                    UNION ALL
                    
                    SELECT 'eia_production' AS data_source,
                        COUNT(*) AS article_count,
                        MAX(date) AS newest_article,
                        MAX(collected_at) AS last_crawled
                    FROM oil_production
                    
                    UNION ALL
                    
                    SELECT 'fred' AS data_source,
                        COUNT(*) AS article_count,
                        MAX(date) AS newest_article,
                        MAX(collected_at) AS last_crawled
                    FROM macro_indicators
                ),
                log_stats AS (
                    SELECT source,
                        COUNT(*) AS total_runs,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_runs,
                        SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_runs,
                        ROUND(AVG(CASE WHEN status = 'success' THEN duration_ms END)::numeric) AS avg_duration_ms,
                        MAX(completed_at) AS last_log_at
                    FROM collection_logs
                    GROUP BY source
                )
                SELECT
                    sf.data_source,
                    sf.article_count,
                    sf.newest_article,
                    sf.last_crawled,
                    ls.total_runs,
                    ls.success_runs,
                    ls.error_runs,
                    ls.avg_duration_ms,
                    ls.last_log_at
                FROM source_freshness sf
                LEFT JOIN log_stats ls ON (
                    CASE
                        WHEN sf.data_source IN ('nyt', 'guardian', 'gnews', 'newsapi', 'gdelt', 'naver_news', 'naver_crawl') THEN 'news'
                        WHEN sf.data_source IN ('eia_inventory', 'eia_production') THEN 'eia'
                        ELSE sf.data_source
                    END = ls.source
                )
                ORDER BY sf.article_count DESC
            """))
            return [dict(r._mapping) for r in result.all()]

    async def get_news_integrity_report(self) -> dict:
        """데이터 완결성 검증 리포트"""
        session_factory = get_session_factory()
        async with session_factory() as session:
            # 1. 요약 통계
            summary = await session.execute(text("""
                SELECT
                    SUM(CASE WHEN title IS NULL OR title = '' THEN 1 ELSE 0 END) AS no_title,
                    SUM(CASE WHEN description IS NULL OR description = '' THEN 1 ELSE 0 END) AS no_desc,
                    SUM(CASE WHEN url IS NULL OR url = '' THEN 1 ELSE 0 END) AS no_url,
                    SUM(CASE WHEN published_at IS NULL THEN 1 ELSE 0 END) AS no_date,
                    SUM(CASE WHEN is_classified = 1 AND classification_result IS NULL THEN 1 ELSE 0 END) AS cls_broken,
                    SUM(CASE WHEN hold_status = 1 THEN 1 ELSE 0 END) AS held,
                    SUM(CASE WHEN hold_status = 2 THEN 1 ELSE 0 END) AS manual_input
                FROM news_articles
            """))
            summary_row = dict(summary.one()._mapping)

            # 2. 중복 URL 수
            dup_result = await session.execute(text("""
                SELECT COUNT(*) AS dup_count FROM (
                    SELECT url FROM news_articles GROUP BY url HAVING COUNT(*) > 1
                ) sub
            """))
            summary_row["dup_urls"] = dup_result.scalar() or 0

            # 3. 문제 기사 목록 (최대 50건)
            problems = await session.execute(text("""
                SELECT id, title, description, url, data_source, published_at, hold_status,
                    CASE
                        WHEN title IS NULL OR title = '' THEN 'no_title'
                        WHEN description IS NULL OR description = '' THEN 'no_desc'
                        WHEN is_classified = 1 AND classification_result IS NULL THEN 'cls_broken'
                        ELSE 'other'
                    END AS issue_type
                FROM news_articles
                WHERE (title IS NULL OR title = '')
                    OR (description IS NULL OR description = '')
                    OR (is_classified = 1 AND classification_result IS NULL)
                ORDER BY collected_at DESC
                LIMIT 50
            """))
            problem_list = [dict(r._mapping) for r in problems.all()]

            return {
                "summary": summary_row,
                "problems": problem_list,
            }

    async def update_news_hold_status(self, article_ids: list[str], hold_status: int) -> int:
        """기사 보류 상태 업데이트"""
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = (
                update(NewsArticleModel)
                .where(NewsArticleModel.id.in_(article_ids))
                .values(hold_status=hold_status)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    async def manual_insert_article(self, data: dict) -> str:
        """관리자 수동 기사 입력"""
        from hashlib import sha256
        session_factory = get_session_factory()
        article_id = data.get("id") or sha256(data["url"].encode()).hexdigest()
        now = datetime.utcnow().isoformat()

        async with session_factory() as session:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt = pg_insert(NewsArticleModel).values(
                id=article_id,
                title=data["title"],
                description=data.get("description", ""),
                source_name=data.get("source_name", "manual"),
                url=data["url"],
                published_at=data.get("published_at", now),
                content_snippet=data.get("description", "")[:200],
                data_source="manual",
                collected_at=now,
                is_classified=0,
                hold_status=2,  # 수동입력 표시
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
            await session.execute(stmt)
            await session.commit()
        return article_id
