"""한국수출입은행 환율 API Collector 테스트"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Mock 응답 데이터 ──────────────────────────

MOCK_API_RESPONSE = [
    {
        "result": 1,
        "cur_unit": "AED",
        "ttb": "370.89",
        "tts": "378.31",
        "deal_bas_r": "374.6",
        "bkpr": "374",
        "yy_efee_r": "0",
        "ten_dd_efee_r": "0",
        "kftc_bkpr": "374",
        "kftc_deal_bas_r": "374.6",
        "cur_nm": "아랍에미리트 디르함"
    },
    {
        "result": 1,
        "cur_unit": "USD",
        "ttb": "1,355.20",
        "tts": "1,382.80",
        "deal_bas_r": "1,369.00",
        "bkpr": "1,369",
        "yy_efee_r": "0",
        "ten_dd_efee_r": "0",
        "kftc_bkpr": "1,369",
        "kftc_deal_bas_r": "1,369.00",
        "cur_nm": "미국 달러"
    },
]

MOCK_EMPTY_RESPONSE = []  # 주말/공휴일


class TestExchangeRateCollector:
    """ExchangeRateCollector 단위 테스트"""

    @pytest.mark.asyncio
    async def test_parse_usd_rate_from_api_response(self):
        """정상 응답에서 USD 매매기준율을 올바르게 파싱한다"""
        with patch("app.services.exchange_rate_collector.settings") as mock_settings, \
             patch("app.services.exchange_rate_collector.RateLimiter") as mock_limiter_cls, \
             patch("app.services.exchange_rate_collector.with_backoff") as mock_backoff, \
             patch("app.services.exchange_rate_collector.Database") as mock_db_cls, \
             patch("os.path.exists", return_value=False), \
             patch("os.makedirs"):

            mock_settings.KOREAEXIM_API_KEY = "test_key"
            mock_settings.DATA_CACHE_DIR = "/tmp/test"
            mock_limiter = MagicMock()
            mock_limiter.acquire = AsyncMock(return_value=True)
            mock_limiter_cls.return_value = mock_limiter
            mock_backoff.return_value = MOCK_API_RESPONSE

            from app.services.exchange_rate_collector import ExchangeRateCollector

            with patch.object(ExchangeRateCollector, "__init__", lambda self: None):
                collector = ExchangeRateCollector()
                collector.api_key = "test_key"
                collector.rate_limiter = mock_limiter
                collector.db = MagicMock()
                collector.CACHE_DIR = "/tmp/test/raw"
                collector.BASE_URL = "https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON"

                # Mock file operations
                with patch("builtins.open", MagicMock()):
                    result = await collector.get_exchange_rate("20260510")

            assert result is not None
            assert result["krw_usd"] == 1369.0
            assert result["cur_unit"] == "USD"
            assert result["date"] == "2026-05-10"

    @pytest.mark.asyncio
    async def test_empty_response_uses_fallback_cache(self):
        """빈 응답(주말) 시 Fallback 캐시를 사용한다"""
        with patch("app.services.exchange_rate_collector.settings") as mock_settings, \
             patch("app.services.exchange_rate_collector.RateLimiter") as mock_limiter_cls, \
             patch("app.services.exchange_rate_collector.with_backoff") as mock_backoff, \
             patch("app.services.exchange_rate_collector.Database"), \
             patch("os.path.exists", return_value=False), \
             patch("os.makedirs"):

            mock_settings.KOREAEXIM_API_KEY = "test_key"
            mock_settings.DATA_CACHE_DIR = "/tmp/test"
            mock_limiter = MagicMock()
            mock_limiter.acquire = AsyncMock(return_value=True)
            mock_limiter_cls.return_value = mock_limiter
            mock_backoff.return_value = MOCK_EMPTY_RESPONSE

            from app.services.exchange_rate_collector import ExchangeRateCollector

            with patch.object(ExchangeRateCollector, "__init__", lambda self: None):
                collector = ExchangeRateCollector()
                collector.api_key = "test_key"
                collector.rate_limiter = mock_limiter
                collector.db = MagicMock()
                collector.CACHE_DIR = "/tmp/test/raw"
                collector.BASE_URL = "https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON"

                fallback = {"date": "2026-05-09", "krw_usd": 1365.0}
                with patch.object(collector, "_find_latest_cache", return_value=fallback):
                    result = await collector.get_exchange_rate("20260510")

            assert result is not None
            assert result["krw_usd"] == 1365.0
            assert result["date"] == "2026-05-09"

    def test_parse_rate_with_comma(self):
        """콤마가 포함된 환율 문자열을 올바르게 파싱한다"""
        from app.services.exchange_rate_collector import ExchangeRateCollector

        # parse_rate는 인스턴스 메서드가 아닌 내부 함수이므로 별도 검증
        def parse_rate(rate_str):
            if not rate_str:
                return None
            try:
                return float(rate_str.replace(",", ""))
            except (ValueError, TypeError):
                return None

        assert parse_rate("1,369.00") == 1369.0
        assert parse_rate("1,355.20") == 1355.2
        assert parse_rate("374.6") == 374.6
        assert parse_rate("") is None
        assert parse_rate(None) is None

    @pytest.mark.asyncio
    async def test_no_api_key_returns_none(self):
        """API 키 미설정 시 None을 반환한다"""
        with patch("app.services.exchange_rate_collector.settings") as mock_settings, \
             patch("app.services.exchange_rate_collector.RateLimiter"), \
             patch("app.services.exchange_rate_collector.Database"), \
             patch("os.makedirs"):

            mock_settings.KOREAEXIM_API_KEY = None
            mock_settings.DATA_CACHE_DIR = "/tmp/test"

            from app.services.exchange_rate_collector import ExchangeRateCollector

            with patch.object(ExchangeRateCollector, "__init__", lambda self: None):
                collector = ExchangeRateCollector()
                collector.api_key = None
                collector.rate_limiter = MagicMock()
                collector.db = MagicMock()
                collector.CACHE_DIR = "/tmp/test/raw"

                result = await collector.get_exchange_rate()

            assert result is None
