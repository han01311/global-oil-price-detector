import pytest
import respx
from httpx import Response
from unittest.mock import patch

from app.services.data_collector import DataCollector
from app.schemas.price import PriceHistory, MacroHistory

# Mock data from other tests
from .test_eia_collector import MOCK_WTI_RESPONSE, MOCK_BRENT_RESPONSE
from .test_fred_collector import MOCK_FEDFUNDS_RESPONSE, MOCK_DOLLAR_INDEX_RESPONSE
from .test_news_collector import MOCK_NEWSAPI_RESPONSE, MOCK_GDELT_RESPONSE

@pytest.mark.asyncio
@respx.mock
async def test_full_collection_flow(monkeypatch):
    """DataCollector를 통한 전체 수집 흐름이 정상 동작하는지 테스트"""
    # Setup: Ensure all API keys are present
    monkeypatch.setattr("app.services.data_collector.settings.EIA_API_KEY", "TEST_EIA")
    monkeypatch.setattr("app.services.data_collector.settings.FRED_API_KEY", "TEST_FRED")
    monkeypatch.setattr("app.services.data_collector.settings.NEWS_API_KEY", "TEST_NEWS")

    # Mock all external APIs
    # EIA
    respx.get(url__regex=r".*eia.gov.*PET\.RWTC\.D.*").mock(return_value=Response(200, json=MOCK_WTI_RESPONSE))
    respx.get(url__regex=r".*eia.gov.*PET\.RBRTE\.D.*").mock(return_value=Response(200, json=MOCK_BRENT_RESPONSE))
    # FRED
    respx.get(url__regex=r".*fred/series/observations.*FEDFUNDS.*").mock(return_value=Response(200, json=MOCK_FEDFUNDS_RESPONSE))
    respx.get(url__regex=r".*fred/series/observations.*DTWEXBGS.*").mock(return_value=Response(200, json=MOCK_DOLLAR_INDEX_RESPONSE))
    # Mock other FRED series to return empty
    respx.get(url__regex=r".*fred/series/observations.*").mock(return_value=Response(200, json={"observations": []}))
    # News
    respx.get(url__regex=r".*newsapi.org.*").mock(return_value=Response(200, json=MOCK_NEWSAPI_RESPONSE))
    respx.get(url__regex=r".*gdeltproject.org.*").mock(return_value=Response(200, json=MOCK_GDELT_RESPONSE))

    collector = DataCollector()
    result = await collector.collect_all(start_date="2023-10-26", end_date="2023-10-27")

    # Assertions
    assert "prices" in result
    assert "macro" in result
    assert "news" in result

    # Check prices
    assert isinstance(result["prices"], PriceHistory)
    assert len(result["prices"].prices) == 2
    assert result["prices"].prices[0].wti == 83.21

    # Check macro
    assert isinstance(result["macro"], MacroHistory)
    assert len(result["macro"].indicators) > 0
    assert result["macro"].indicators[0].dollar_index is not None

    # Check news (3 unique articles)
    assert isinstance(result["news"], list)
    assert len(result["news"]) == 3


@pytest.mark.asyncio
@respx.mock
async def test_cache_usage_in_collect_all(monkeypatch, tmp_path):
    """collect_all 호출 시 캐시가 올바르게 동작하는지 테스트"""
    monkeypatch.setattr("app.services.data_collector.settings.EIA_API_KEY", "TEST_EIA")
    monkeypatch.setattr("app.services.data_collector.settings.FRED_API_KEY", "TEST_FRED")
    monkeypatch.setattr("app.services.data_collector.settings.NEWS_API_KEY", "TEST_NEWS")

    # Mock routes
    eia_route = respx.get(url__regex=r".*eia.gov.*").mock(return_value=Response(200, json={"response": {"data": []}}))
    fred_route = respx.get(url__regex=r".*fred/series/observations.*").mock(return_value=Response(200, json={"observations": []}))
    news_route = respx.get(url__regex=r".*newsapi.org.*").mock(return_value=Response(200, json={"articles": []}))
    gdelt_route = respx.get(url__regex=r".*gdeltproject.org.*").mock(return_value=Response(200, json={"articles": []}))

    # Patch cache directory for all collectors
    with patch('app.services.data_collector.BaseCollector.cache_dir', tmp_path):
        collector = DataCollector()

        # First call - should hit the APIs
        await collector.collect_all(start_date="2024-01-01", end_date="2024-01-02")
        
        assert eia_route.call_count > 0
        assert fred_route.call_count > 0
        assert news_route.call_count > 0
        assert gdelt_route.call_count > 0

        # Reset call counts
        eia_route.reset()
        fred_route.reset()
        news_route.reset()
        gdelt_route.reset()

        # Second call - should use cache
        await collector.collect_all(start_date="2024-01-01", end_date="2024-01-02")

        assert eia_route.call_count == 0
        assert fred_route.call_count == 0
        assert news_route.call_count == 0
        assert gdelt_route.call_count == 0


@pytest.mark.asyncio
@respx.mock
async def test_api_key_missing_handling(monkeypatch):
    """API 키 누락 시 그레이스풀하게 처리되는지 테스트"""
    # Setup: Mock all APIs, but unset FRED key
    monkeypatch.setattr("app.services.data_collector.settings.EIA_API_KEY", "TEST_EIA")
    monkeypatch.setattr("app.services.data_collector.settings.FRED_API_KEY", None) # Key is missing
    monkeypatch.setattr("app.services.data_collector.settings.NEWS_API_KEY", "TEST_NEWS")

    # Mock APIs that should be called
    respx.get(url__regex=r".*eia.gov.*").mock(return_value=Response(200, json=MOCK_WTI_RESPONSE))
    respx.get(url__regex=r".*newsapi.org.*").mock(return_value=Response(200, json=MOCK_NEWSAPI_RESPONSE))
    respx.get(url__regex=r".*gdeltproject.org.*").mock(return_value=Response(200, json=MOCK_GDELT_RESPONSE))
    
    # This route should not be called
    fred_route = respx.get(url__regex=r".*fred/series/observations.*").mock(return_value=Response(200, json={"observations": []}))

    collector = DataCollector()
    assert collector.fred is None # Check that collector was not initialized

    result = await collector.collect_all(start_date="2023-10-26", end_date="2023-10-27")

    # Assertions
    assert fred_route.call_count == 0
    
    # Check that other data was collected successfully
    assert isinstance(result["prices"], PriceHistory)
    assert len(result["prices"].prices) > 0
    assert isinstance(result["news"], list)
    assert len(result["news"]) > 0

    # Check that macro data is empty but in the correct format
    assert isinstance(result["macro"], MacroHistory)
    assert result["macro"].indicators == []
