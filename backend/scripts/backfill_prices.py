"""
과거 유가 데이터 종합 백필 스크립트 (캐시 우회)

소스:
  - EIA API v2: WTI (1986~), Brent (1987~) — 일별 (직접 HTTP 호출, 캐시 안 씀)
  - FRED API: Dubai Fateh (POILDUBUSDM, 1992~) — 월별 → 일별 보간

사용법:
    python3 scripts/backfill_prices.py                   # 전체 (1970~현재)
    python3 scripts/backfill_prices.py --start 2000      # 2000년부터
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time

import httpx
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.database import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def fetch_eia_series(series_id: str, start_date: str, end_date: str) -> list[dict]:
    """EIA API v2에서 시리즈 데이터를 직접 수집 (캐시 없이)"""
    params = {
        "api_key": settings.EIA_API_KEY,
        "frequency": "daily",
        "data[0]": "value",
        "facets[series][]": series_id,
        "start": start_date,
        "end": end_date,
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "offset": 0,
        "length": 5000,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get("https://api.eia.gov/v2/petroleum/pri/spt/data/", params=params)
        resp.raise_for_status()
        data = resp.json()

    return data.get("response", {}).get("data", [])


async def fetch_eia_prices(start_year: int, end_year: int) -> pd.DataFrame:
    """EIA에서 WTI/Brent 일별 가격 수집 (연도별 직접 호출)"""
    if not settings.EIA_API_KEY:
        logger.warning("EIA_API_KEY가 없습니다.")
        return pd.DataFrame(columns=["date", "wti", "brent"])

    all_wti = []
    all_brent = []

    for year in range(start_year, end_year + 1):
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"

        try:
            wti_data = await fetch_eia_series("RWTC", start_date, end_date)
            brent_data = await fetch_eia_series("RBRTE", start_date, end_date)

            all_wti.extend(wti_data)
            all_brent.extend(brent_data)

            wti_cnt = len(wti_data)
            brent_cnt = len(brent_data)

            if wti_cnt > 0 or brent_cnt > 0:
                logger.info(f"  EIA {year}: WTI {wti_cnt}건, Brent {brent_cnt}건")
            else:
                logger.info(f"  EIA {year}: 데이터 없음")

            # Rate limit: EIA는 초당 제한이 있음
            await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"  EIA {year} 실패: {e}")
            await asyncio.sleep(1)

    # DataFrame 변환
    wti_df = pd.DataFrame(columns=["date", "wti"])
    brent_df = pd.DataFrame(columns=["date", "brent"])

    if all_wti:
        wti_df = pd.DataFrame(all_wti)[["period", "value"]].rename(columns={"period": "date", "value": "wti"})
        wti_df["wti"] = pd.to_numeric(wti_df["wti"], errors="coerce")

    if all_brent:
        brent_df = pd.DataFrame(all_brent)[["period", "value"]].rename(columns={"period": "date", "value": "brent"})
        brent_df["brent"] = pd.to_numeric(brent_df["brent"], errors="coerce")

    if wti_df.empty and brent_df.empty:
        return pd.DataFrame(columns=["date", "wti", "brent"])

    df = pd.merge(wti_df, brent_df, on="date", how="outer")
    return df.sort_values("date").drop_duplicates(subset="date")


async def fetch_fred_dubai(start_year: int, end_year: int) -> pd.DataFrame:
    """FRED에서 Dubai Fateh 월별 가격 수집 → 일별 보간"""
    if not settings.FRED_API_KEY:
        logger.warning("FRED_API_KEY가 없습니다.")
        return pd.DataFrame(columns=["date", "dubai"])

    start_date = f"{start_year}-01-01"
    end_date = f"{end_year}-12-31"

    try:
        params = {
            "series_id": "POILDUBUSDM",
            "api_key": settings.FRED_API_KEY,
            "file_type": "json",
            "observation_start": start_date,
            "observation_end": end_date,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get("https://api.stlouisfed.org/fred/series/observations", params=params)
            resp.raise_for_status()
            data = resp.json()

        obs = data.get("observations", [])
        if not obs:
            logger.warning("FRED Dubai 데이터 없음")
            return pd.DataFrame(columns=["date", "dubai"])

        df = pd.DataFrame(obs)[["date", "value"]]
        df = df[df["value"] != "."]
        df = df.rename(columns={"value": "dubai"})
        df["dubai"] = pd.to_numeric(df["dubai"], errors="coerce")

        logger.info(f"  FRED Dubai: {len(df)}건 (월별)")

        # 월별 → 일별 보간 (forward-fill)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df = df.resample("D").ffill()
        df = df.reset_index()
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")

        logger.info(f"  FRED Dubai 보간 후: {len(df)}건 (일별)")
        return df

    except Exception as e:
        logger.error(f"FRED Dubai 실패: {e}")
        return pd.DataFrame(columns=["date", "dubai"])


async def backfill(start_year: int, end_year: int):
    db = Database()
    await db.connect()

    logger.info(f"📊 유가 백필 시작: {start_year}~{end_year}")
    logger.info("=" * 50)

    # 1. EIA에서 WTI/Brent 수집
    logger.info("🔹 EIA WTI/Brent 수집 중...")
    eia_df = await fetch_eia_prices(start_year, end_year)
    logger.info(f"   EIA 합계: {len(eia_df)}건")

    # 2. FRED에서 Dubai 수집
    logger.info("🔹 FRED Dubai 수집 중...")
    dubai_df = await fetch_fred_dubai(start_year, end_year)
    logger.info(f"   Dubai 합계: {len(dubai_df)}건")

    # 3. 병합
    if eia_df.empty and dubai_df.empty:
        logger.error("❌ 수집된 데이터가 없습니다.")
        return

    if not eia_df.empty and not dubai_df.empty:
        merged = pd.merge(eia_df, dubai_df, on="date", how="outer")
    elif not eia_df.empty:
        merged = eia_df
        merged["dubai"] = None
    else:
        merged = dubai_df
        merged["wti"] = None
        merged["brent"] = None

    merged = merged.sort_values("date").drop_duplicates(subset="date")
    merged = merged[(merged["date"] >= f"{start_year}-01-01") & (merged["date"] <= f"{end_year}-12-31")]

    # NaN → None
    merged = merged.where(pd.notnull(merged), None)

    logger.info(f"📦 병합된 레코드: {len(merged)}건")
    logger.info(f"   날짜 범위: {merged['date'].iloc[0]} ~ {merged['date'].iloc[-1]}")

    wti_count = merged["wti"].notna().sum()
    brent_count = merged["brent"].notna().sum()
    dubai_count = merged["dubai"].notna().sum()
    logger.info(f"   WTI: {wti_count}건, Brent: {brent_count}건, Dubai: {dubai_count}건")

    # 4. DB에 저장 (source='opinet'으로 통일)
    records = merged.to_dict("records")
    for r in records:
        r["source"] = "opinet"

    await db.upsert_oil_prices(records)

    logger.info(f"🎯 백필 완료! {len(records)}건 저장됨")

    # 5. 결과 확인
    conn = await db.get_conn()
    async with conn.execute("SELECT COUNT(*) as cnt FROM oil_prices") as c:
        row = await c.fetchone()
        logger.info(f"   DB 총 유가 레코드: {row['cnt']}건")

    async with conn.execute(
        "SELECT MIN(date) as min_d, MAX(date) as max_d FROM oil_prices"
    ) as c:
        row = await c.fetchone()
        logger.info(f"   DB 날짜 범위: {row['min_d']} ~ {row['max_d']}")

    # 연도별 분포 확인
    async with conn.execute("""
        SELECT SUBSTR(date,1,4) as y, COUNT(*) as cnt, 
               SUM(CASE WHEN wti IS NOT NULL THEN 1 ELSE 0 END) as wti_cnt,
               SUM(CASE WHEN brent IS NOT NULL THEN 1 ELSE 0 END) as brent_cnt,
               SUM(CASE WHEN dubai IS NOT NULL THEN 1 ELSE 0 END) as dubai_cnt
        FROM oil_prices GROUP BY y ORDER BY y
    """) as c:
        rows = await c.fetchall()
        logger.info("   연도별 분포:")
        for r in rows:
            logger.info(f"     {r['y']}: {r['cnt']}건 (WTI:{r['wti_cnt']}, Brent:{r['brent_cnt']}, Dubai:{r['dubai_cnt']})")

    await db.close()


def main():
    parser = argparse.ArgumentParser(description="과거 유가 종합 백필 (EIA + FRED Dubai)")
    parser.add_argument("--start", type=int, default=1970, help="시작 연도 (기본: 1970)")
    parser.add_argument("--end", type=int, default=2026, help="종료 연도")
    args = parser.parse_args()

    asyncio.run(backfill(args.start, args.end))


if __name__ == "__main__":
    main()
