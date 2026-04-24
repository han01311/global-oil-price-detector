"""
EIA 데이터 수집기 테스트
"""
from datetime import datetime
import pytest
import respx
import httpx
from httpx import Response

from app.services.data_collector import EIACollector

# Mock EIA API responses
MOCK_WTI_RESPONSE = {
    "response": {
        "total": 2,
        "data": [
            {"period": "2023-10-27", "seriesId": "PET.RWTC.D", "value": 85.54},
            {"period": "2023-10-26", "seriesId": "PET.RWTC.D", "value": 83.21},
        ],
    }
}

MOCK_BRENT_RESPONSE = {
    "response": {
        "total": 2,
        "data": [
            {"period": "2023-10-27", "seriesId": "PET.RBRTE.D", "value": 90.48},
            {"period": "2023-10-26", "seriesId": "PET.RBRTE.D", "value": 87.93},
        ],
    }
}

MOCK_INVENTORY_RESPONSE = {
    "response": {
        "total": 1,
        "data": [
            {"period": "2023-10-20", "seriesId": "PET.WCESTUS1.W", "value": 421093},
        ],
    }
}

MOCK_PRODUCTION_RESPONSE = {
    "response": {
        "total": 1,
        "data": [
            {"period": "2023-10-20", "seriesId": "PET.WCRFPUS2.W", "value": 13200},
        ],
    }
}


@pytest.fixture
def eia_collector():
    """테스트용 EIACollector 인스턴스"""
    return EIACollector(api_key="TEST_KEY")


@pytest.mark.asyncio
@respx.mock
async def test_get_crude_prices_success(eia_collector):
    """유가 데이터를 성공적으로 가져오는지 테스트"""
    respx.get(url__regex=r".*PET\.RWTC\.D.*").mock(return_value=Response(200, json=MOCK_WTI_RESPONSE))
    respx.get(url__regex=r".*PET\.RBRTE\.D.*").mock(return_value=Response(200, json=MOCK_BRENT_RESPONSE))

    df = await eia_collector.get_crude_prices("2023-10-26", "2023-10-27")

    assert not df.empty
    assert list(df.columns) == ['date', 'wti', 'brent']
    assert len(df) == 2
    assert df.loc[0, 'date'] == '2023-10-26'
    assert df.loc[0, 'wti'] == 83.21
    assert df.loc[1, 'brent'] == 90.48


def test_missing_api_key(monkeypatch):
    """API 키가 없을 때 초기화 에러가 발생하는지 테스트"""
    monkeypatch.setattr("app.services.data_collector.settings.EIA_API_KEY", None)
    with pytest.raises(ValueError, match="EIA_API_KEY is required"):
        EIACollector()


@pytest.mark.asyncio
@respx.mock
async def test_caching_logic(eia_collector, tmp_path):
    """데이터가 캐시되고 재사용되는지 테스트"""
    eia_collector.cache_dir = tmp_path

    wti_route = respx.get(url__regex=r".*PET\.RWTC\.D.*").mock(return_value=Response(200, json=MOCK_WTI_RESPONSE))
    brent_route = respx.get(url__regex=r".*PET\.RBRTE\.D.*").mock(return_value=Response(200, json=MOCK_BRENT_RESPONSE))

    # 첫 번째 호출: API 호출
    await eia_collector.get_crude_prices("2023-10-26", "2023-10-27")
    assert wti_route.call_count == 1
    assert brent_route.call_count == 1

    # 캐시 파일 생성 확인
    today = datetime.now().strftime('%Y-%m-%d')
    assert (tmp_path / f"{today}_PET.RWTC.D.json").exists()
    assert (tmp_path / f"{today}_PET.RBRTE.D.json").exists()

    # 두 번째 호출: 캐시 사용
    df = await eia_collector.get_crude_prices("2023-10-26", "2023-10-27")
    assert wti_route.call_count == 1  # 추가 호출 없음
    assert brent_route.call_count == 1  # 추가 호출 없음
    assert len(df) == 2


@pytest.mark.asyncio
@respx.mock
async def test_get_crude_inventory(eia_collector):
    """원유 재고 데이터를 성공적으로 가져오는지 테스트"""
    inventory_route = respx.get(url__regex=r".*PET\.WCESTUS1\.W.*").mock(return_value=Response(200, json=MOCK_INVENTORY_RESPONSE))

    df = await eia_collector.get_crude_inventory("2023-10-20", "2023-10-20")

    assert inventory_route.call_count == 1
    assert not df.empty
    assert list(df.columns) == ['date', 'inventory_mbbl']
    assert df.loc[0, 'inventory_mbbl'] == 421093


@pytest.mark.asyncio
@respx.mock
async def test_get_production(eia_collector):
    """원유 생산량 데이터를 성공적으로 가져오는지 테스트"""
    production_route = respx.get(url__regex=r".*PET\.WCRFPUS2\.W.*").mock(return_value=Response(200, json=MOCK_PRODUCTION_RESPONSE))

    df = await eia_collector.get_production("2023-10-20", "2023-10-20")

    assert production_route.call_count == 1
    assert not df.empty
    assert list(df.columns) == ['date', 'production_mbbl_d']
    assert df.loc[0, 'production_mbbl_d'] == 13200


@pytest.mark.asyncio
@respx.mock
async def test_api_error_handling(eia_collector):
    """API 에러 발생 시 예외 처리가 되는지 테스트"""
    respx.get(url__regex=r".*").mock(return_value=Response(500))

    with pytest.raises(httpx.HTTPStatusError):
        await eia_collector.get_crude_prices("2023-01-01", "2023-01-02")
