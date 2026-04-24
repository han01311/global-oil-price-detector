import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone, timedelta

from app.main import app
from app.schemas.news import NewsArticle, ClassifiedArticle

@pytest.fixture
def client():
    """테스트 클라이언트"""
    return TestClient(app)

# --- Existing Tests for /latest ---

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

# --- New Tests for /classify, /similar, /factors/summary ---

@patch('app.api.news.NewsClassifier', autospec=True)
def test_classify_news_with_body(MockNewsClassifier, client):
    """POST /api/news/classify (body) 성공 케이스"""
    mock_classifier_instance = MockNewsClassifier.return_value
    mock_classifier_instance.model = True # Simulate model is available
    mock_classifier_instance.classify_batch = AsyncMock(return_value=[
        ClassifiedArticle(article=NewsArticle(id="1", title="T1", url="u", published_at="p", data_source="d"), is_relevant=True, category="supply", impact_score=3, impact_summary="s", confidence=0.9, classified_at="t")
    ])
    
    articles_payload = [{"id": "1", "title": "T1", "url": "u", "published_at": "p", "data_source": "d", "description": None, "source": None, "content_snippet": None}]
    response = client.post("/api/news/classify", json=articles_payload)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]['category'] == 'supply'
    mock_classifier_instance.classify_batch.assert_awaited_once()

@patch('app.api.news.NewsClassifier', autospec=True)
@patch('app.api.news.DataCollector', autospec=True)
def test_classify_news_with_fetch_latest(MockDataCollector, MockNewsClassifier, client):
    """POST /api/news/classify (fetch_latest) 성공 케이스"""
    mock_collector_instance = MockDataCollector.return_value
    mock_collector_instance.collect_news = AsyncMock(return_value=[{"id": "1", "title": "T1", "url": "u", "published_at": "p", "data_source": "d"}])
    
    mock_classifier_instance = MockNewsClassifier.return_value
    mock_classifier_instance.model = True
    mock_classifier_instance.classify_batch = AsyncMock(return_value=[])

    response = client.post("/api/news/classify?fetch_latest=true")

    assert response.status_code == 200
    mock_collector_instance.collect_news.assert_awaited_once()
    mock_classifier_instance.classify_batch.assert_awaited_once()

def test_classify_news_bad_request(client):
    """POST /api/news/classify 파라미터 누락 시 400 에러"""
    response = client.post("/api/news/classify")
    assert response.status_code == 400

@patch('app.api.news.MarketMemory', autospec=True)
def test_search_similar_events_success(MockMarketMemory, client):
    """GET /api/news/similar 성공 케이스"""
    mock_memory_instance = MockMarketMemory.return_value
    mock_memory_instance.is_available.return_value = True
    mock_memory_instance.search_similar = AsyncMock(return_value=[
        {
            "id": "event1",
            "document": "Title: Big Oil News\nSummary: A summary of the news.",
            "metadata": {
                "category": "geopolitics", "impact_score": 5, "date": "2024-01-01", "url": "http://a.com",
                "wti_change_1d": 2.5, "wti_change_7d": 5.0, "wti_change_30d": -1.0
            },
            "distance": 0.1
        }
    ])

    response = client.get("/api/news/similar?query=oil&category=geopolitics")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]['title'] == "Big Oil News"
    assert data[0]['category'] == "geopolitics"
    assert data[0]['wti_change_30d'] is None # Check -1.0 conversion
    assert data[0]['similarity'] == pytest.approx(0.9)
    mock_memory_instance.search_similar.assert_awaited_once_with(query="oil", category="geopolitics", n_results=5)

def test_search_similar_events_missing_query(client):
    """GET /api/news/similar 쿼리 누락 시 422 에러"""
    response = client.get("/api/news/similar")
    assert response.status_code == 422

@patch('app.api.news.MarketMemory', autospec=True)
def test_get_factor_summary_success(MockMarketMemory, client):
    """GET /api/news/factors/summary 성공 케이스"""
    mock_memory_instance = MockMarketMemory.return_value
    mock_memory_instance.is_available.return_value = True
    
    today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    old_day_str = (datetime.now(timezone.utc) - timedelta(days=2)).strftime('%Y-%m-%d')

    mock_collection = mock_memory_instance._collection
    mock_collection.get.return_value = {
        "metadatas": [
            {"date": today_str, "category": "supply", "impact_score": 3},
            {"date": today_str, "category": "supply", "impact_score": 1},
            {"date": yesterday_str, "category": "demand", "impact_score": -2},
            {"date": old_day_str, "category": "geopolitics", "impact_score": 4}, # Should be excluded
        ]
    }

    response = client.get("/api/news/factors/summary")

    assert response.status_code == 200
    data = response.json()
    
    assert "factors" in data
    assert "overall_sentiment" in data
    
    # Only today's and yesterday's events should be included
    assert len(data['factors']) == 2
    
    supply_factor = next(f for f in data['factors'] if f['category'] == 'supply')
    demand_factor = next(f for f in data['factors'] if f['category'] == 'demand')

    assert supply_factor['article_count'] == 2
    assert supply_factor['avg_score'] == 2.0 # (3+1)/2
    assert supply_factor['trend'] == 'bullish'
    
    assert demand_factor['article_count'] == 1
    assert demand_factor['avg_score'] == -2.0
    assert demand_factor['trend'] == 'bearish'

    # (3 + 1 - 2) / 3 = 2/3 = 0.666...
    assert data['overall_sentiment'] == pytest.approx(0.67)
