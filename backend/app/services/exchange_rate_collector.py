"""한국수출입은행 환율 API Collector (공공데이터 data.go.kr)

API 문서: https://www.koreaexim.go.kr/ir/HPHKIR020M01?apino=2&viewtype=C
엔드포인트: https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON
인증: authkey 파라미터 (API 키)
Rate Limit: 1,000회/일
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, date
from typing import Optional

import httpx

from app.core.config import settings
from app.core.database import Database
from app.services.rate_limiter import RateLimiter, with_backoff

logger = logging.getLogger(__name__)


class ExchangeRateCollector:
    """한국수출입은행 환율 API를 호출하여 원/달러 매매기준율을 수집한다."""

    BASE_URL = "https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON"
    CACHE_DIR = os.path.join(settings.DATA_CACHE_DIR, "raw")

    def __init__(self):
        self.api_key = settings.KOREAEXIM_API_KEY
        self.rate_limiter = RateLimiter()
        self.db = Database()
        os.makedirs(self.CACHE_DIR, exist_ok=True)

    def _get_cache_path(self, search_date: str) -> str:
        return os.path.join(self.CACHE_DIR, f"{search_date}_krw_usd.json")

    def _find_latest_cache(self) -> Optional[dict]:
        """가장 최근의 환율 캐시 파일을 찾아 반환 (주말/공휴일 Fallback용)"""
        try:
            files = [
                os.path.join(self.CACHE_DIR, f)
                for f in os.listdir(self.CACHE_DIR)
                if f.endswith("_krw_usd.json")
            ]
            if not files:
                return None
            latest = max(files, key=os.path.getmtime)
            with open(latest, "r") as f:
                data = json.load(f)
                logger.info(f"[ExchangeRate] Fallback 캐시 로드: {latest}")
                return data
        except Exception as e:
            logger.error(f"[ExchangeRate] 캐시 로드 실패: {e}")
            return None

    async def get_exchange_rate(self, search_date: str | None = None) -> Optional[dict]:
        """원/달러 환율을 조회하여 반환한다.

        Args:
            search_date: 조회 날짜 (YYYYMMDD). None이면 당일.

        Returns:
            {"date": "2026-05-10", "krw_usd": 1360.0, "cur_unit": "USD", ...}
        """
        if not self.api_key:
            logger.warning("[ExchangeRate] KOREAEXIM_API_KEY가 설정되지 않았습니다.")
            return None

        today_str = search_date or datetime.now().strftime("%Y%m%d")
        cache_date = f"{today_str[:4]}-{today_str[4:6]}-{today_str[6:8]}"
        cache_path = self._get_cache_path(cache_date)

        # 캐시 확인
        if os.path.exists(cache_path):
            with open(cache_path, "r") as f:
                cached = json.load(f)
                if cached:
                    logger.info(f"[ExchangeRate] 캐시 사용: {cache_date}")
                    return cached

        # Rate Limit 체크
        can_proceed = await self.rate_limiter.acquire("koreaexim")
        if not can_proceed:
            logger.warning("[ExchangeRate] Rate limit 초과. Fallback 캐시 사용.")
            return self._find_latest_cache()

        # API 호출
        params = {
            "authkey": self.api_key,
            "searchdate": today_str,
            "data": "AP01",
        }

        async def do_fetch():
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                return response.json()

        try:
            data = await with_backoff("koreaexim", do_fetch)
        except Exception as e:
            logger.error(f"[ExchangeRate] API 호출 실패: {e}")
            return self._find_latest_cache()

        # 응답 파싱: [{ cur_unit: "USD", deal_bas_r: "1,360.00", result: 1, ... }, ...]
        if not data or not isinstance(data, list):
            logger.warning(f"[ExchangeRate] 빈 응답 (주말/공휴일 가능). Fallback 캐시 사용.")
            return self._find_latest_cache()

        # result 코드 확인 (1=성공, 2=코드오류, 3=인증오류, 4=일일한도)
        first = data[0] if data else {}
        result_code = first.get("result")
        if result_code and result_code != 1:
            logger.error(f"[ExchangeRate] API 에러 코드: {result_code}")
            return self._find_latest_cache()

        # USD 항목 찾기
        usd_entry = None
        for entry in data:
            if entry.get("cur_unit") == "USD":
                usd_entry = entry
                break

        if not usd_entry:
            logger.warning("[ExchangeRate] USD 데이터 없음.")
            return self._find_latest_cache()

        # deal_bas_r: 매매기준율 (콤마 포함 문자열 → float)
        def parse_rate(rate_str: str) -> Optional[float]:
            if not rate_str:
                return None
            try:
                return float(rate_str.replace(",", ""))
            except (ValueError, TypeError):
                return None

        result = {
            "date": cache_date,
            "krw_usd": parse_rate(usd_entry.get("deal_bas_r")),
            "ttb": parse_rate(usd_entry.get("ttb")),        # 전신환(송금) 매입률
            "tts": parse_rate(usd_entry.get("tts")),        # 전신환(송금) 매도율
            "cur_unit": "USD",
            "cur_nm": usd_entry.get("cur_nm", "미국 달러"),
            "source": "koreaexim_public",
        }

        # 캐시 저장
        with open(cache_path, "w") as f:
            json.dump(result, f, ensure_ascii=False)

        logger.info(f"[ExchangeRate] 환율 수집 완료: {cache_date} → {result['krw_usd']}원")
        return result

    async def collect_and_store(self, search_date: str | None = None) -> Optional[dict]:
        """환율 수집 후 DB(macro_indicators)에 저장한다."""
        rate_data = await self.get_exchange_rate(search_date)
        if not rate_data or rate_data.get("krw_usd") is None:
            return None

        # macro_indicators 테이블에 저장 (source='koreaexim'으로 분리)
        await self.db.upsert_macro_indicators([{
            "date": rate_data["date"],
            "krw_usd": rate_data["krw_usd"],
            "source": "koreaexim",
        }])

        return rate_data
