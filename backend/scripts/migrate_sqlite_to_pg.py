#!/usr/bin/env python3
"""
SQLite → PostgreSQL 데이터 마이그레이션 스크립트

기존 petro_ax.db의 모든 데이터를 PostgreSQL로 이관합니다.
PostgreSQL의 ON CONFLICT (upsert)를 사용하므로 중복 데이터는 안전하게 처리됩니다.

Usage:
    cd backend && python3 scripts/migrate_sqlite_to_pg.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import sqlite3
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("EIA_API_KEY", "migration")
os.environ.setdefault("FRED_API_KEY", "migration")

from app.core.database import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SQLITE_PATH = Path(__file__).resolve().parent.parent / "data" / "petro_ax.db"


def read_sqlite_table(db_path: Path, table: str) -> list[dict]:
    """SQLite 테이블의 모든 행을 dict 리스트로 반환"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(f"SELECT * FROM {table}")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


async def migrate():
    if not SQLITE_PATH.exists():
        logger.error(f"SQLite 파일을 찾을 수 없습니다: {SQLITE_PATH}")
        sys.exit(1)

    logger.info(f"소스 DB: {SQLITE_PATH}")
    logger.info("PostgreSQL 연결 중...")

    db = Database()
    await db.connect()

    # ── 1. 유가 데이터 ──
    logger.info("=== oil_prices 마이그레이션 시작 ===")
    oil_rows = read_sqlite_table(SQLITE_PATH, "oil_prices")
    logger.info(f"  SQLite에서 {len(oil_rows)}건 로드")

    # 배치 처리 (500건씩)
    batch_size = 500
    total_upserted = 0
    for i in range(0, len(oil_rows), batch_size):
        batch = oil_rows[i:i + batch_size]
        count = await db.upsert_oil_prices(batch)
        total_upserted += count
        logger.info(f"  배치 {i // batch_size + 1}: {count}건 upsert")
    logger.info(f"  ✅ oil_prices 완료: {total_upserted}건")

    # ── 2. 뉴스 기사 ──
    logger.info("=== news_articles 마이그레이션 시작 ===")
    news_rows = read_sqlite_table(SQLITE_PATH, "news_articles")
    logger.info(f"  SQLite에서 {len(news_rows)}건 로드")

    # source_name 필드 매핑 (SQLite에서는 source_name으로 저장, upsert에서 source로 참조)
    for row in news_rows:
        if "source_name" in row and "source" not in row:
            row["source"] = row["source_name"]

    total_upserted = 0
    for i in range(0, len(news_rows), batch_size):
        batch = news_rows[i:i + batch_size]
        count = await db.upsert_news_articles(batch)
        total_upserted += count
        logger.info(f"  배치 {i // batch_size + 1}: {count}건 upsert")
    logger.info(f"  ✅ news_articles 완료: {total_upserted}건")

    # ── 3. 재고 데이터 ──
    logger.info("=== oil_inventory 마이그레이션 시작 ===")
    inv_rows = read_sqlite_table(SQLITE_PATH, "oil_inventory")
    logger.info(f"  SQLite에서 {len(inv_rows)}건 로드")
    count = await db.upsert_oil_inventory(inv_rows)
    logger.info(f"  ✅ oil_inventory 완료: {count}건")

    # ── 4. 생산량 데이터 ──
    logger.info("=== oil_production 마이그레이션 시작 ===")
    prod_rows = read_sqlite_table(SQLITE_PATH, "oil_production")
    logger.info(f"  SQLite에서 {len(prod_rows)}건 로드")
    count = await db.upsert_oil_production(prod_rows)
    logger.info(f"  ✅ oil_production 완료: {count}건")

    # ── 5. 거시경제 지표 ──
    logger.info("=== macro_indicators 마이그레이션 시작 ===")
    macro_rows = read_sqlite_table(SQLITE_PATH, "macro_indicators")
    logger.info(f"  SQLite에서 {len(macro_rows)}건 로드")
    count = await db.upsert_macro_indicators(macro_rows)
    logger.info(f"  ✅ macro_indicators 완료: {count}건")

    # ── 6. 수집 로그 ──
    logger.info("=== collection_logs 마이그레이션 시작 ===")
    log_rows = read_sqlite_table(SQLITE_PATH, "collection_logs")
    logger.info(f"  SQLite에서 {len(log_rows)}건 로드")
    migrated_logs = 0
    for log in log_rows:
        try:
            await db.insert_collection_log(log)
            migrated_logs += 1
        except Exception as e:
            logger.warning(f"  로그 마이그레이션 실패 (무시): {e}")
    logger.info(f"  ✅ collection_logs 완료: {migrated_logs}건")

    # ── 검증 ──
    logger.info("")
    logger.info("=== 마이그레이션 결과 검증 ===")
    overview = await db.get_overview()
    for table_name, stats in overview.items():
        logger.info(f"  {table_name}: {stats['count']}건")

    await db.close()
    logger.info("")
    logger.info("🎉 마이그레이션 완료!")


if __name__ == "__main__":
    asyncio.run(migrate())
