"""공공데이터 API 엔드포인트 통합 테스트"""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestPublicDataAPI:
    """공공데이터 API 라우트 테스트"""

    @pytest.mark.asyncio
    async def test_exchange_rate_endpoint(self):
        """GET /api/public-data/exchange-rate 가 정상 응답한다"""
        mock_rate = {
            "date": "2026-05-10",
            "krw_usd": 1369.0,
            "ttb": 1355.2,
            "tts": 1382.8,
            "cur_unit": "USD",
            "cur_nm": "미국 달러",
            "source": "koreaexim_public",
        }

        with patch("app.api.public_data.ExchangeRateCollector") as mock_cls:
            mock_collector = mock_cls.return_value
            mock_collector.get_exchange_rate = AsyncMock(return_value=mock_rate)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/api/public-data/exchange-rate")

            assert response.status_code == 200
            data = response.json()
            assert data["krw_usd"] == 1369.0
            assert data["cur_unit"] == "USD"

    @pytest.mark.asyncio
    async def test_data_sources_endpoint(self):
        """GET /api/public-data/data-sources 가 3개 데이터 소스를 반환한다"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/public-data/data-sources")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 3
        assert len(data["public_data_sources"]) == 3

        # 각 소스의 필수 필드 확인
        for source in data["public_data_sources"]:
            assert "name" in source
            assert "provider" in source
            assert "portal" in source
            assert source["portal"] == "data.go.kr"

    @pytest.mark.asyncio
    async def test_import_concentration_endpoint(self):
        """GET /api/public-data/import-concentration 가 HHI 데이터를 반환한다"""
        mock_hhi = {
            "year": 2024,
            "hhi": 2150.5,
            "risk_level": "medium",
            "top_countries": [
                {"country": "사우디아라비아", "share_pct": 30.5, "volume": 140641}
            ],
            "total_volume": 331025,
            "country_count": 25,
            "source": "knoc_public",
        }

        with patch("app.api.public_data.ImportConcentrationService") as mock_cls:
            mock_service = mock_cls.return_value
            mock_service.calculate_hhi = AsyncMock(return_value=mock_hhi)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/api/public-data/import-concentration")

            assert response.status_code == 200
            data = response.json()
            assert data["hhi"] == 2150.5
            assert data["risk_level"] == "medium"
            assert len(data["top_countries"]) > 0
