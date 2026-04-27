from __future__ import annotations

"""
SQLite 비동기 데이터베이스 관리 모듈
수집된 데이터의 영구 저장 및 관리자 조회를 담당한다.
"""
import aiosqlite
import logging
import os
from datetime import datetime
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 테이블 스키마 정의
# ──────────────────────────────────────────────
SCHEMA_SQL = """
-- 유가 데이터 (EIA)
CREATE TABLE IF NOT EXISTS oil_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    dubai REAL,
    wti REAL,
    brent REAL,
    source TEXT DEFAULT 'opinet',
    collected_at TEXT NOT NULL,
    UNIQUE(date, source)
);

-- 원유 재고 (EIA)
CREATE TABLE IF NOT EXISTS oil_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    inventory_mbbl REAL,
    collected_at TEXT NOT NULL,
    UNIQUE(date)
);

-- 원유 생산량 (EIA)
CREATE TABLE IF NOT EXISTS oil_production (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    production_mbbl_d REAL,
    collected_at TEXT NOT NULL,
    UNIQUE(date)
);

-- 거시경제 지표 (FRED)
CREATE TABLE IF NOT EXISTS macro_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    fed_rate REAL,
    dollar_index REAL,
    source TEXT DEFAULT 'fred',
    collected_at TEXT NOT NULL,
    UNIQUE(date, source)
);

-- 뉴스 기사 (NewsAPI, GNews, GDELT)
CREATE TABLE IF NOT EXISTS news_articles (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    source_name TEXT,
    url TEXT NOT NULL,
    published_at TEXT,
    content_snippet TEXT,
    data_source TEXT,
    collected_at TEXT NOT NULL,
    is_classified INTEGER DEFAULT 0
);

-- 수집 작업 이력
CREATE TABLE IF NOT EXISTS collection_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL,
    records_count INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_ms INTEGER
);

-- Rate Limit 카운터 (일별)
CREATE TABLE IF NOT EXISTS rate_limit_counters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    date TEXT NOT NULL,
    request_count INTEGER DEFAULT 0,
    last_request_at TEXT,
    UNIQUE(source, date)
);
"""


class Database:
    """비동기 SQLite 데이터베이스 싱글톤"""

    _instance: "Database | None" = None
    _db: aiosqlite.Connection | None = None

    def __new__(cls) -> "Database":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def db_path(self) -> str:
        if os.path.isabs(settings.DATABASE_PATH):
            return settings.DATABASE_PATH
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        return os.path.join(backend_dir, settings.DATABASE_PATH)

    async def connect(self) -> None:
        """DB 연결 및 테이블 초기화"""
        if self._db is not None:
            return

        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA_SQL)
        await self._db.commit()
        logger.info(f"SQLite DB connected: {self.db_path}")

    async def close(self) -> None:
        """DB 연결 종료"""
        if self._db:
            await self._db.close()
            self._db = None
            Database._instance = None
            logger.info("SQLite DB closed.")

    async def get_conn(self) -> aiosqlite.Connection:
        """연결 반환 (없으면 자동 연결)"""
        if self._db is None:
            await self.connect()
        assert self._db is not None
        return self._db

    # ──────────────────────────────────────────────
    # 유가 데이터 CRUD
    # ──────────────────────────────────────────────

    async def upsert_oil_prices(self, rows: list[dict]) -> int:
        """유가 데이터를 upsert (date+source 기준 중복 무시)"""
        conn = await self.get_conn()
        now = datetime.utcnow().isoformat()
        count = 0
        for row in rows:
            try:
                await conn.execute(
                    "INSERT OR REPLACE INTO oil_prices (date, dubai, wti, brent, source, collected_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (row["date"], row.get("dubai"), row.get("wti"), row.get("brent"), row.get("source", "opinet"), now),
                )
                count += 1
            except Exception as e:
                logger.warning(f"Failed to upsert oil_price row {row.get('date')}: {e}")
        await conn.commit()
        return count

    async def get_oil_prices(
        self, start_date: str | None = None, end_date: str | None = None,
        limit: int = 500, offset: int = 0
    ) -> list[dict]:
        """유가 데이터 조회"""
        conn = await self.get_conn()
        query = "SELECT * FROM oil_prices WHERE 1=1"
        params: list[Any] = []
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_oil_prices_count(self) -> int:
        conn = await self.get_conn()
        async with conn.execute("SELECT COUNT(*) as cnt FROM oil_prices") as cursor:
            row = await cursor.fetchone()
        return row["cnt"] if row else 0

    # ──────────────────────────────────────────────
    # 재고 CRUD
    # ──────────────────────────────────────────────

    async def upsert_oil_inventory(self, rows: list[dict]) -> int:
        conn = await self.get_conn()
        now = datetime.utcnow().isoformat()
        count = 0
        for row in rows:
            try:
                await conn.execute(
                    "INSERT OR REPLACE INTO oil_inventory (date, inventory_mbbl, collected_at) "
                    "VALUES (?, ?, ?)",
                    (row["date"], row.get("inventory_mbbl"), now),
                )
                count += 1
            except Exception as e:
                logger.warning(f"Failed to upsert inventory row: {e}")
        await conn.commit()
        return count

    async def get_oil_inventory(
        self, start_date: str | None = None, end_date: str | None = None,
        limit: int = 500, offset: int = 0
    ) -> list[dict]:
        conn = await self.get_conn()
        query = "SELECT * FROM oil_inventory WHERE 1=1"
        params: list[Any] = []
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_oil_inventory_count(self) -> int:
        conn = await self.get_conn()
        async with conn.execute("SELECT COUNT(*) as cnt FROM oil_inventory") as cursor:
            row = await cursor.fetchone()
        return row["cnt"] if row else 0

    # ──────────────────────────────────────────────
    # 생산량 CRUD
    # ──────────────────────────────────────────────

    async def upsert_oil_production(self, rows: list[dict]) -> int:
        conn = await self.get_conn()
        now = datetime.utcnow().isoformat()
        count = 0
        for row in rows:
            try:
                await conn.execute(
                    "INSERT OR REPLACE INTO oil_production (date, production_mbbl_d, collected_at) "
                    "VALUES (?, ?, ?)",
                    (row["date"], row.get("production_mbbl_d"), now),
                )
                count += 1
            except Exception as e:
                logger.warning(f"Failed to upsert production row: {e}")
        await conn.commit()
        return count

    async def get_oil_production_count(self) -> int:
        conn = await self.get_conn()
        async with conn.execute("SELECT COUNT(*) as cnt FROM oil_production") as cursor:
            row = await cursor.fetchone()
        return row["cnt"] if row else 0

    # ──────────────────────────────────────────────
    # 거시 경제 CRUD
    # ──────────────────────────────────────────────

    async def upsert_macro_indicators(self, rows: list[dict]) -> int:
        conn = await self.get_conn()
        now = datetime.utcnow().isoformat()
        count = 0
        for row in rows:
            try:
                await conn.execute(
                    "INSERT OR REPLACE INTO macro_indicators (date, fed_rate, dollar_index, source, collected_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (row["date"], row.get("fed_rate"), row.get("dollar_index"), row.get("source", "fred"), now),
                )
                count += 1
            except Exception as e:
                logger.warning(f"Failed to upsert macro row: {e}")
        await conn.commit()
        return count

    async def get_macro_indicators(
        self, start_date: str | None = None, end_date: str | None = None,
        limit: int = 500, offset: int = 0
    ) -> list[dict]:
        conn = await self.get_conn()
        query = "SELECT * FROM macro_indicators WHERE 1=1"
        params: list[Any] = []
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_macro_indicators_count(self) -> int:
        conn = await self.get_conn()
        async with conn.execute("SELECT COUNT(*) as cnt FROM macro_indicators") as cursor:
            row = await cursor.fetchone()
        return row["cnt"] if row else 0

    # ──────────────────────────────────────────────
    # 뉴스 CRUD
    # ──────────────────────────────────────────────

    async def upsert_news_articles(self, articles: list[dict]) -> int:
        conn = await self.get_conn()
        now = datetime.utcnow().isoformat()
        count = 0
        for a in articles:
            try:
                await conn.execute(
                    "INSERT OR IGNORE INTO news_articles "
                    "(id, title, description, source_name, url, published_at, content_snippet, data_source, collected_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        a["id"], a["title"], a.get("description"), a.get("source"),
                        a["url"], a.get("published_at"), a.get("content_snippet"),
                        a.get("data_source"), now,
                    ),
                )
                count += 1
            except Exception as e:
                logger.warning(f"Failed to upsert news article: {e}")
        await conn.commit()
        return count

    async def get_news_articles(
        self, data_source: str | None = None,
        limit: int = 50, offset: int = 0
    ) -> list[dict]:
        conn = await self.get_conn()
        query = "SELECT * FROM news_articles WHERE 1=1"
        params: list[Any] = []
        if data_source:
            query += " AND data_source = ?"
            params.append(data_source)
        query += " ORDER BY published_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_news_articles_count(self, data_source: str | None = None) -> int:
        conn = await self.get_conn()
        query = "SELECT COUNT(*) as cnt FROM news_articles"
        params: list[Any] = []
        if data_source:
            query += " WHERE data_source = ?"
            params.append(data_source)
        async with conn.execute(query, params) as cursor:
            row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def get_news_source_stats(self) -> list[dict]:
        """뉴스 기사 소스별 통계 (건수, 최초/최근 수집일)"""
        conn = await self.get_conn()
        query = """
            SELECT 
                data_source,
                COUNT(*) as count,
                MIN(published_at) as oldest_date,
                MAX(published_at) as newest_date,
                COUNT(DISTINCT source_name) as source_count
            FROM news_articles
            GROUP BY data_source
            ORDER BY count DESC
        """
        async with conn.execute(query) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_news_yearly_stats(self) -> list[dict]:
        """뉴스 기사 연도별 통계"""
        conn = await self.get_conn()
        query = """
            SELECT 
                SUBSTR(published_at, 1, 4) as year,
                data_source,
                COUNT(*) as count
            FROM news_articles
            WHERE published_at IS NOT NULL
            GROUP BY year, data_source
            ORDER BY year ASC
        """
        async with conn.execute(query) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ──────────────────────────────────────────────
    # 수집 로그 CRUD
    # ──────────────────────────────────────────────

    async def insert_collection_log(self, log: dict) -> int:
        conn = await self.get_conn()
        async with conn.execute(
            "INSERT INTO collection_logs "
            "(source, task_type, status, records_count, error_message, started_at, completed_at, duration_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                log["source"], log["task_type"], log["status"],
                log.get("records_count", 0), log.get("error_message"),
                log["started_at"], log.get("completed_at"),
                log.get("duration_ms"),
            ),
        ) as cursor:
            log_id = cursor.lastrowid
        await conn.commit()
        return log_id or 0

    async def get_collection_logs(
        self, source: str | None = None, status: str | None = None,
        limit: int = 50, offset: int = 0
    ) -> list[dict]:
        conn = await self.get_conn()
        query = "SELECT * FROM collection_logs WHERE 1=1"
        params: list[Any] = []
        if source:
            query += " AND source = ?"
            params.append(source)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_collection_logs_count(
        self, source: str | None = None, status: str | None = None
    ) -> int:
        conn = await self.get_conn()
        query = "SELECT COUNT(*) as cnt FROM collection_logs WHERE 1=1"
        params: list[Any] = []
        if source:
            query += " AND source = ?"
            params.append(source)
        if status:
            query += " AND status = ?"
            params.append(status)
        async with conn.execute(query, params) as cursor:
            row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def get_log_stats_by_source(self) -> list[dict]:
        """소스별 최근 로그 통계"""
        conn = await self.get_conn()
        query = """
        SELECT
            source,
            COUNT(*) as total_runs,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count,
            SUM(CASE WHEN status = 'rate_limited' THEN 1 ELSE 0 END) as rate_limited_count,
            MAX(completed_at) as last_run_at,
            SUM(records_count) as total_records
        FROM collection_logs
        GROUP BY source
        ORDER BY source
        """
        async with conn.execute(query) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ──────────────────────────────────────────────
    # Rate Limit 카운터 CRUD
    # ──────────────────────────────────────────────

    async def increment_rate_counter(self, source: str) -> int:
        """Rate limit 카운터 증가, 현재 카운트 반환"""
        conn = await self.get_conn()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        now = datetime.utcnow().isoformat()

        await conn.execute(
            "INSERT INTO rate_limit_counters (source, date, request_count, last_request_at) "
            "VALUES (?, ?, 1, ?) "
            "ON CONFLICT(source, date) DO UPDATE SET "
            "request_count = request_count + 1, last_request_at = ?",
            (source, today, now, now),
        )
        await conn.commit()

        async with conn.execute(
            "SELECT request_count FROM rate_limit_counters WHERE source = ? AND date = ?",
            (source, today),
        ) as cursor:
            row = await cursor.fetchone()
        return row["request_count"] if row else 1

    async def get_rate_counter(self, source: str) -> dict:
        """현재 일일 Rate limit 카운터 조회"""
        conn = await self.get_conn()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        async with conn.execute(
            "SELECT request_count, last_request_at FROM rate_limit_counters "
            "WHERE source = ? AND date = ?",
            (source, today),
        ) as cursor:
            row = await cursor.fetchone()
        if row:
            return {"source": source, "date": today, "request_count": row["request_count"], "last_request_at": row["last_request_at"]}
        return {"source": source, "date": today, "request_count": 0, "last_request_at": None}

    async def get_all_rate_counters(self) -> list[dict]:
        """모든 소스의 오늘 Rate limit 카운터"""
        conn = await self.get_conn()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        async with conn.execute(
            "SELECT source, request_count, last_request_at FROM rate_limit_counters WHERE date = ?",
            (today,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [{"source": r["source"], "date": today, "request_count": r["request_count"], "last_request_at": r["last_request_at"]} for r in rows]

    # ──────────────────────────────────────────────
    # Overview 통계
    # ──────────────────────────────────────────────

    async def get_overview(self) -> dict:
        """전체 DB 현황 통계"""
        conn = await self.get_conn()
        tables = {
            "oil_prices": "SELECT COUNT(*) as cnt, MAX(collected_at) as last_collected FROM oil_prices",
            "oil_inventory": "SELECT COUNT(*) as cnt, MAX(collected_at) as last_collected FROM oil_inventory",
            "oil_production": "SELECT COUNT(*) as cnt, MAX(collected_at) as last_collected FROM oil_production",
            "macro_indicators": "SELECT COUNT(*) as cnt, MAX(collected_at) as last_collected FROM macro_indicators",
            "news_articles": "SELECT COUNT(*) as cnt, MAX(collected_at) as last_collected FROM news_articles",
            "collection_logs": "SELECT COUNT(*) as cnt, MAX(completed_at) as last_collected FROM collection_logs",
        }
        overview = {}
        for table_name, query in tables.items():
            async with conn.execute(query) as cursor:
                row = await cursor.fetchone()
            overview[table_name] = {
                "count": row["cnt"] if row else 0,
                "last_collected": row["last_collected"] if row else None,
            }
        return overview
