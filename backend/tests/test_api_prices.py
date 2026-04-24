import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.main import app
from app.schemas.price import PriceHistory, OilPrice, MacroHistory

@pytest.fixture
def client():
    """테스트 클라이언트"""
    return TestClient(app)

@patch('app.api.prices.DataCollector', autospec=True)
def test_get_price_history_success(MockDataCollector, client):
    """/api/prices/history 성공 케이스 테스트"""
    # Mock setup
    mock_instance = MockDataCollector.return_value
    mock_instance.collect_prices = AsyncMock(return_value=PriceHistory(
        prices=[
            OilPrice(date="2024-01-01", wti=71.65, brent=77.04),
            OilPrice(date="2024-01-02", wti=70.38, brent=75.89),
        ],
        source="eia",
        last_updated="2024-01-03T00:00:00Z"
    ))

    # API call
    response = client.get("/api/prices/history?start_date=2024-01-01&end_date=2024-01-02")

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data['source'] == 'eia'
    assert len(data['prices']) == 2
    assert data['prices'][0]['date'] == '2024-01-01'
    mock_instance.collect_prices.assert_awaited_once_with("2024-01-01", "2024-01-02")

@patch('app.api.prices.DataCollector', autospec=True)
def test_get_latest_prices_success(MockDataCollector, client):
    """/api/prices/latest 성공 케이스 테스트"""
    # Mock setup
    mock_instance = MockDataCollector.return_value
    mock_instance.collect_prices = AsyncMock(return_value=PriceHistory(
        prices=[
            OilPrice(date="2024-01-01", wti=71.65, brent=77.04),
            OilPrice(date="2024-01-02", wti=70.38, brent=75.89),
        ],
        source="eia",
        last_updated="2024-01-03T00:00:00Z"
    ))

    # API call
    response = client.get("/api/prices/latest")

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data['date'] == '2024-01-02' # Should return the last one
    assert data['wti'] == 70.38
    mock_instance.collect_prices.assert_awaited_once()

@patch('app.api.prices.DataCollector', autospec=True)
def test_get_macro_indicators_success(MockDataCollector, client):
    """/api/prices/macro 성공 케이스 테스트"""
    # Mock setup
    mock_instance = MockDataCollector.return_value
    mock_instance.collect_macro_data = AsyncMock(return_value=MacroHistory(
        indicators=[
            {"date": "2024-01-01", "fed_rate": 5.33, "dollar_index": 101.3},
            {"date": "2024-01-02", "fed_rate": 5.33, "dollar_index": 102.2},
        ],
        source="fred",
        last_updated="2024-01-03T00:00:00Z"
    ))

    # API call
    response = client.get("/api/prices/macro?start_date=2024-01-01&end_date=2024-01-02")

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data['source'] == 'fred'
    assert len(data['indicators']) == 2
    assert data['indicators'][0]['dollar_index'] == 101.3
    mock_instance.collect_macro_data.assert_awaited_once_with("2024-01-01", "2024-01-02")

def test_get_price_history_invalid_date(client):
    """잘못된 날짜 형식에 대해 422 에러를 반환하는지 테스트"""
    response = client.get("/api/prices/history?start_date=2024-1-1&end_date=2024-01-02")
    assert response.status_code == 422 # Unprocessable Entity

    response = client.get("/api/prices/history?start_date=2024-01-01") # Missing end_date
    assert response.status_code == 422
