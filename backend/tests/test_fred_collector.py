"""
FRED 데이터 수집기 테스트
"""
from datetime import datetime
import pytest
import respx
import httpx
from httpx import Response

from app.services.data_collector import FREDCollector

# Mock FRED API responses
MOCK_FEDFUNDS_RESPONSE = {
    "observations": [
        {"realtime_start": "2023-11-01", "realtime_end": "2023-11-01", "date": "2023-09-01", "value": "5.33"},
        {"realtime_start": "2023-11-01", "realtime_end": "2023-11-01", "date": "2023-10-01", "value": "5.33"}
    ]
}

MOCK_DOLLAR_INDEX_RESPONSE = {
    "observations": [
        {"realtime_start": "2023-11-01", "realtime_end": "2023-11-01", "date": "2023-10-26", "value": "106.4063"},
        {"realtime_start": "2023-11-01", "realtime_end": "2023-11-01", "date": "2023-10-27", "value": "106.4111"},
        {"realtime_start": "2023-11-01", "realtime_end": "2023-11-01", "date": "2023-10-28", "value": "."} # Weekend, no data
    ]
}

@pytest.fixture
def fred_collector(tmp_path):
    """테스트용 FREDCollector 인스턴스"""
    collector = FREDCollector(api_key="TEST_KEY")
    collector.cache_dir = tmp_path
    return collector


def test_missing_api_key(monkeypatch):
    """API 키가 없을 때 초기화 에러가 발생하는지 테스트"""
    monkeypatch.setattr("app.services.data_collector.settings.FRED_API_KEY", None)
    with pytest.raises(ValueError, match="FRED_API_KEY is required"):
        FREDCollector()

@pytest.mark.asyncio
@respx.mock
async def test_get_series_success(fred_collector):
    """단일 시리즈를 성공적으로 가져오는지 테스트"""
    respx.get(url__regex=r".*fred/series/observations.*FEDFUNDS.*").mock(return_value=Response(200, json=MOCK_FEDFUNDS_RESPONSE))

    df = await fred_collector.get_series("FEDFUNDS", "fed_rate", "2023-09-01", "2023-10-31")

    assert not df.empty
    assert list(df.columns) == ['date', 'fed_rate']
    assert len(df) == 2
    assert df.loc[0, 'date'] == '2023-09-01'
    assert df.loc[0, 'fed_rate'] == 5.33

@pytest.mark.asyncio
@respx.mock
async def test_get_macro_indicators_merge(fred_collector):
    """일별/월별 데이터를 올바르게 병합하는지 테스트"""
    # Mock all series used in get_macro_indicators
    for name, series_id in fred_collector.MACRO_SERIES.items():
        if series_id == "FEDFUNDS":
            respx.get(url__regex=f".*{series_id}.*").mock(return_value=Response(200, json=MOCK_FEDFUNDS_RESPONSE))
        elif series_id == "DTWEXBGS":
            respx.get(url__regex=f".*{series_id}.*").mock(return_value=Response(200, json=MOCK_DOLLAR_INDEX_RESPONSE))
        else:
            # Mock empty for others to avoid errors
            respx.get(url__regex=f".*{series_id}.*").mock(return_value=Response(200, json={"observations": []}))

    df = await fred_collector.get_macro_indicators("2023-10-26", "2023-10-28")

    assert not df.empty
    assert 'date' in df.columns
    assert 'fed_rate' in df.columns
    assert 'dollar_index' in df.columns
    assert len(df) == 2 # Only dates with at least one value

    # Check dollar index values (daily)
    assert df[df['date'] == '2023-10-26']['dollar_index'].iloc[0] == 106.4063
    assert df[df['date'] == '2023-10-27']['dollar_index'].iloc[0] == 106.4111

    # Check fed rate values (monthly, forward-filled)
    # The value from 2023-10-01 should be filled forward
    assert df[df['date'] == '2023-10-26']['fed_rate'].iloc[0] == 5.33
    assert df[df['date'] == '2023-10-27']['fed_rate'].iloc[0] == 5.33

@pytest.mark.asyncio
@respx.mock
async def test_caching_logic(fred_collector, tmp_path):
    """데이터가 캐시되고 재사용되는지 테스트"""
    fred_collector.cache_dir = tmp_path

    route = respx.get(url__regex=r".*FEDFUNDS.*").mock(return_value=Response(200, json=MOCK_FEDFUNDS_RESPONSE))

    # 첫 번째 호출: API 호출
    await fred_collector.get_series("FEDFUNDS", "fed_rate", "2023-01-01", "2023-01-31")
    assert route.call_count == 1

    # 캐시 파일 생성 확인
    today = datetime.now().strftime('%Y-%m-%d')
    assert (tmp_path / f"{today}_FEDFUNDS.json").exists()

    # 두 번째 호출: 캐시 사용
    await fred_collector.get_series("FEDFUNDS", "fed_rate", "2023-01-01", "2023-01-31")
    assert route.call_count == 1  # 추가 호출 없음

@pytest.mark.asyncio
@respx.mock
async def test_api_error_handling(fred_collector):
    """API 에러 발생 시 예외 처리가 되는지 테스트"""
    respx.get(url__regex=r".*").mock(return_value=Response(500))

    with pytest.raises(httpx.HTTPStatusError):
        await fred_collector.get_series("FEDFUNDS", "fed_rate", "2023-01-01", "2023-01-02")
