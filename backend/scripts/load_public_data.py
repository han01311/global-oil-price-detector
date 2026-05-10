#!/usr/bin/env python3
"""data.go.kr 공공데이터 CSV를 PostgreSQL에 적재하는 스크립트.

한국석유공사 파일데이터 2종을 파싱하여 DB에 upsert 합니다.
CSV 파일은 EUC-KR 인코딩이므로 자동 감지합니다.

사용법:
    # 원유수입 국가별 CSV 적재
    python scripts/load_public_data.py --imports backend/data/public/한국석유공사_국내\ 원유수입_국가별_20241231.csv

    # 세계 원유 수출입 물량 CSV 적재
    python scripts/load_public_data.py --trade backend/data/public/한국석유공사_세계\ 원유\ 수출입\ 물량_20241231.csv

    # 둘 다 적재 (기본 경로)
    python scripts/load_public_data.py --all
"""
import argparse
import asyncio
import csv
import logging
import os
import re
import sys
from datetime import datetime
from typing import Optional, List

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import Database
from app.models.base import get_session_factory
from app.models.oil_import import OilImport
from app.models.world_oil_trade import WorldOilTrade

from sqlalchemy.dialects.postgresql import insert as pg_insert

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_IMPORTS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "public",
    "한국석유공사_국내 원유수입_국가별_20241231.csv"
)
DEFAULT_TRADE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "public",
    "한국석유공사_세계 원유 수출입 물량_20241231.csv"
)


def read_csv_with_encoding(filepath: str) -> List[List[str]]:
    """EUC-KR 또는 UTF-8로 CSV 파일을 읽는다."""
    for encoding in ["euc-kr", "cp949", "utf-8", "utf-8-sig"]:
        try:
            with open(filepath, "r", encoding=encoding) as f:
                reader = csv.reader(f)
                rows = [row for row in reader]
                if rows:
                    logger.info(f"CSV 읽기 성공: {filepath} (인코딩: {encoding}, {len(rows)}행)")
                    return rows
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"CSV 인코딩 감지 실패: {filepath}")


def parse_float(value: str) -> Optional[float]:
    """숫자 문자열을 float으로 변환. 빈 값은 None."""
    if not value or not value.strip():
        return None
    try:
        return float(value.strip().replace(",", ""))
    except ValueError:
        return None


async def load_oil_imports(filepath: str):
    """국내 원유수입 국가별 CSV를 DB에 적재한다.

    CSV 구조:
    - 헤더: 년, 중국(물량), 중국(금액), 중국(단가), 필리핀(물량), ...
    - 행: 연도별 데이터 (1980~2024)
    - 각 국가당 3개 컬럼: (물량), (금액), (단가)
    """
    rows = read_csv_with_encoding(filepath)
    if not rows:
        logger.error("CSV 데이터가 비어있습니다.")
        return

    headers = [h.strip() for h in rows[0]]

    # 헤더에서 국가명 추출: "중국(물량)" → "중국"
    countries = []
    for i in range(1, len(headers), 3):
        if i < len(headers):
            match = re.match(r"(.+?)\(물량\)", headers[i])
            if match:
                countries.append((match.group(1), i))  # (국가명, 시작 인덱스)

    logger.info(f"파싱된 국가 수: {len(countries)}")
    logger.info(f"국가 목록: {[c[0] for c in countries]}")

    db = Database()
    await db.connect()
    session_factory = get_session_factory()
    now = datetime.utcnow().isoformat()

    total_count = 0
    async with session_factory() as session:
        for row in rows[1:]:
            if not row or not row[0].strip():
                continue

            year = int(row[0].strip())

            for country_name, start_idx in countries:
                volume = parse_float(row[start_idx]) if start_idx < len(row) else None
                value = parse_float(row[start_idx + 1]) if start_idx + 1 < len(row) else None
                unit_price = parse_float(row[start_idx + 2]) if start_idx + 2 < len(row) else None

                # 모든 값이 None이면 건너뛰기
                if volume is None and value is None and unit_price is None:
                    continue

                stmt = pg_insert(OilImport).values(
                    year=year,
                    country=country_name,
                    import_volume=volume,
                    import_value=value,
                    unit_price=unit_price,
                    source="knoc_public",
                    collected_at=now,
                )
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_oil_imports_year_country",
                    set_={
                        "import_volume": stmt.excluded.import_volume,
                        "import_value": stmt.excluded.import_value,
                        "unit_price": stmt.excluded.unit_price,
                        "collected_at": stmt.excluded.collected_at,
                    },
                )
                await session.execute(stmt)
                total_count += 1

        await session.commit()

    logger.info(f"✅ 원유수입 데이터 적재 완료: {total_count}건 ({len(countries)}개국 × {len(rows)-1}년)")


async def load_world_trade(filepath: str):
    """세계 원유 수출입 물량 CSV를 DB에 적재한다.

    CSV 구조:
    - 헤더: 수출국 및 수입국(백만 톤), 캐나다, 멕시코, 미국, ...
    - 행: 수출국(21개 지역)
    - 값: 수입 물량(백만 톤)
    """
    rows = read_csv_with_encoding(filepath)
    if not rows:
        logger.error("CSV 데이터가 비어있습니다.")
        return

    headers = [h.strip() for h in rows[0]]
    importers = headers[1:]  # 수입국/지역 목록

    logger.info(f"수입국/지역 수: {len(importers)}")
    logger.info(f"수입국 목록: {importers}")

    db = Database()
    await db.connect()
    session_factory = get_session_factory()
    now = datetime.utcnow().isoformat()

    total_count = 0
    async with session_factory() as session:
        for row in rows[1:]:
            if not row or not row[0].strip():
                continue

            exporter = row[0].strip()

            for j, importer in enumerate(importers, start=1):
                if j >= len(row):
                    continue
                volume = parse_float(row[j])
                if volume is None:
                    continue

                stmt = pg_insert(WorldOilTrade).values(
                    exporter=exporter,
                    importer=importer,
                    volume_mt=volume,
                    data_year=2024,  # CSV 파일명에서 추출한 최신 연도
                    source="knoc_public",
                    collected_at=now,
                )
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_world_oil_trades",
                    set_={
                        "volume_mt": stmt.excluded.volume_mt,
                        "collected_at": stmt.excluded.collected_at,
                    },
                )
                await session.execute(stmt)
                total_count += 1

        await session.commit()

    logger.info(f"✅ 세계 수출입 물량 적재 완료: {total_count}건 ({len(rows)-1}개 수출국 × {len(importers)}개 수입국)")


async def main():
    parser = argparse.ArgumentParser(description="data.go.kr 공공데이터 CSV → PostgreSQL 적재")
    parser.add_argument("--imports", type=str, help="원유수입 국가별 CSV 경로")
    parser.add_argument("--trade", type=str, help="세계 원유 수출입 물량 CSV 경로")
    parser.add_argument("--all", action="store_true", help="기본 경로의 CSV 모두 적재")
    args = parser.parse_args()

    if args.all:
        args.imports = DEFAULT_IMPORTS_PATH
        args.trade = DEFAULT_TRADE_PATH

    if not args.imports and not args.trade:
        parser.print_help()
        print("\n예시:")
        print("  python scripts/load_public_data.py --all")
        print("  python scripts/load_public_data.py --imports data/public/원유수입.csv")
        return

    if args.imports:
        logger.info(f"📦 원유수입 CSV 적재 시작: {args.imports}")
        await load_oil_imports(args.imports)

    if args.trade:
        logger.info(f"📦 세계 수출입 CSV 적재 시작: {args.trade}")
        await load_world_trade(args.trade)

    logger.info("🎉 공공데이터 적재 완료!")


if __name__ == "__main__":
    asyncio.run(main())
