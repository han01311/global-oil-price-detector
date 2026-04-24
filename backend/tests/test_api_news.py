import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.main import app

@pytest.fixture
def client():
    """테스트 클라이언트"""
    return TestClient(app)

@patch('app.api.news.DataCollector', autospec=True)
def test_get_latest_news_success(MockDataCollector, client):
    """/api/news/latest 성공 케이스 테스트"""
    # Mock setup
    mock_instance = MockDataCollector.return_value
    # The collector returns a list of dicts, not Pydantic models
    mock_instance.collect_news = AsyncMock(return_value=[
        {
            "id": "1", "title": "News 1", "url": "http://news1.com",
            "published_at": "2024-01-02T00:00:00Z", "data_source": "newsapi",
            "description": "d1", "source": "s1", "content_snippet": "cs1"
        },
        {
            "id": "2", "title": "News 2", "url": "http://news2.com",
            "published_at": "2024-01-01T00:00:00Z", "data_source": "gdelt",
            "description": "d2", "source": "s2", "content_snippet": "cs2"
        },
    ])
    # Mock the KEYWORDS attribute
    mock_instance.news.KEYWORDS = ["oil", "gas"]

    # API call
    response = client.get("/api/news/latest?limit=1")

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert len(data['articles']) == 1
    assert data['articles'][0]['title'] == 'News 1' # Should be sorted by date
    assert data['total_count'] == 1
    assert "oil" in data['query_keywords']
    mock_instance.collect_news.assert_awaited_once()

@patch('app.api.news.DataCollector', autospec=True)
def test_get_latest_news_default_limit(MockDataCollector, client):
    """/api/news/latest 기본 limit 테스트"""
    # Mock setup
    mock_articles = [
        {
            "id": str(i), "title": f"News {i}", "url": f"http://news{i}.com",
            "published_at": f"2024-01-01T{i:02d}:00:00Z", "data_source": "newsapi",
            "description": f"d{i}", "source": f"s{i}", "content_snippet": f"cs{i}"
        } for i in range(25)
    ]
    mock_instance = MockDataCollector.return_value
    mock_instance.collect_news = AsyncMock(return_value=mock_articles)
    mock_instance.news.KEYWORDS = []

    # API call
    response = client.get("/api/news/latest")

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert len(data['articles']) == 20 # Default limit
    assert data['total_count'] == 20
