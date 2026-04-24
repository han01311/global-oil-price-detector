import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import json
import pandas as pd
from datetime import datetime, timedelta, timezone

from app.main import app
from app.services.market_memory import MarketMemory
from app.utils.price_utils import calculate_price_changes
from app.schemas.price import PriceHistory, OilPrice

# --- Fixtures ---

@pytest.fixture(scope="module")
def client():
    """A single TestClient instance for the whole module."""
    return TestClient(app)

@pytest.fixture
def temp_chroma_db(tmp_path):
    """Provides a temporary, isolated ChromaDB path for each test."""
    db_path = str(tmp_path / "chroma_integration_test")
    # Ensure the collection is clean before the test
    try:
        import chromadb
        client = chromadb.PersistentClient(path=db_path)
        client.delete_collection(name=MarketMemory.COLLECTION_NAME)
    except Exception:
        pass # Collection might not exist, which is fine
    return db_path

# Mock data for DataCollector
MOCK_NEWS_ARTICLES = [
    { "id": "news-1", "title": "OPEC+ Considers Deeper Production Cuts Amidst Economic Slowdown", "url": "http://a.com/1", "published_at": "2024-07-15T10:00:00Z", "data_source": "newsapi", "description": "...", "source": "Reuters", "content_snippet": "..."},
    { "id": "news-2", "title": "US Federal Reserve Signals Potential Rate Hikes", "url": "http://a.com/2", "published_at": "2024-07-14T10:00:00Z", "data_source": "newsapi", "description": "...", "source": "Bloomberg", "content_snippet": "..."},
    { "id": "news-3", "title": "Hurricane in Gulf of Mexico Disrupts Oil Production", "url": "http://a.com/3", "published_at": "2024-07-13T10:00:00Z", "data_source": "gdelt", "description": "...", "source": "AP", "content_snippet": "..."},
]

def create_mock_price_history():
    dates = pd.to_datetime([datetime(2024, 7, 16) - timedelta(days=i) for i in range(40)])
    prices = [
        OilPrice(date=d.strftime('%Y-%m-%d'), wti=100.0 - i*0.5, brent=105.0 - i*0.5)
        for i, d in enumerate(dates)
    ]
    return PriceHistory(prices=prices, source="eia", last_updated="2024-07-16T00:00:00Z")

MOCK_PRICE_HISTORY = create_mock_price_history()

# Mock data for NewsClassifier (Gemini response)
def mock_gemini_classifier_logic(prompt: str):
    response = MagicMock()
    if "OPEC" in prompt:
        response.text = json.dumps({ "is_relevant": True, "category": "supply", "impact_score": 3, "impact_summary": "OPEC+ 감산 논의는 공급 감소 기대로 유가 상승 요인.", "confidence": 0.9 })
    elif "Federal Reserve" in prompt:
        response.text = json.dumps({ "is_relevant": True, "category": "macro", "impact_score": -2, "impact_summary": "금리 인상 신호는 달러 강세와 수요 둔화 우려로 유가 하락 요인.", "confidence": 0.85 })
    elif "Hurricane" in prompt:
        response.text = json.dumps({ "is_relevant": True, "category": "climate", "impact_score": 2, "impact_summary": "허리케인으로 인한 생산 차질은 단기적 유가 상승 요인.", "confidence": 0.92 })
    else:
        response.text = json.dumps({ "is_relevant": False, "category": "demand", "impact_score": 0, "impact_summary": "관련 없음.", "confidence": 0.99 })
    return asyncio.sleep(0.01, result=response)

# --- Integration Tests ---

@pytest.mark.asyncio
class TestClassifierIntegration:
    """뉴스 분류 파이프라인 전체 흐름 통합 테스트"""

    @patch('app.services.data_collector.DataCollector.collect_news', new_callable=AsyncMock)
    @patch('app.services.data_collector.DataCollector.collect_prices', new_callable=AsyncMock)
    @patch('google.generativeai.GenerativeModel.generate_content_async')
    async def test_full_classification_flow(self, mock_gemini, mock_collect_prices, mock_collect_news, client, temp_chroma_db):
        """뉴스 수집 → 분류 → ChromaDB 적재 → 검색"""
        # --- 1. Setup Mocks ---
        mock_collect_news.return_value = MOCK_NEWS_ARTICLES
        mock_collect_prices.return_value = MOCK_PRICE_HISTORY
        mock_gemini.side_effect = mock_gemini_classifier_logic

        # --- 2. Classify News via API ---
        # Use a real NewsClassifier, which will call the mocked Gemini
        response = client.post("/api/news/classify?fetch_latest=true")
        assert response.status_code == 200
        classified_articles = response.json()
        assert len(classified_articles) == 3
        assert classified_articles[0]['category'] == 'supply'

        # --- 3. Store in MarketMemory ---
        # Use a real MarketMemory with a temporary DB
        memory = MarketMemory(db_path=temp_chroma_db)
        assert memory.is_available()

        prices_df = pd.DataFrame([p.model_dump() for p in MOCK_PRICE_HISTORY.prices])
        for article_data in classified_articles:
            event_date = article_data['article']['published_at'].split('T')[0]
            price_changes = calculate_price_changes(prices_df, event_date)
            await memory.store_event(article_data, price_changes)
        
        import time; await asyncio.sleep(0.5)

        # --- 4. Search via API ---
        # The API should now use the populated MarketMemory
        with patch('app.api.news.MarketMemory', return_value=memory):
            search_response = client.get("/api/news/similar?query=OPEC production cuts")
            assert search_response.status_code == 200
            search_results = search_response.json()

            assert len(search_results) > 0
            assert search_results[0]['category'] == 'supply'
            assert "OPEC" in search_results[0]['title']
            assert 'wti_change_7d' in search_results[0]
            assert search_results[0]['wti_change_7d'] is not None

    @pytest.mark.asyncio
    async def test_factor_summary_accuracy(self, client, temp_chroma_db):
        """요인 요약이 분류된 기사의 통계와 일치하는지 확인"""
        # --- 1. Setup: Manually populate DB ---
        memory = MarketMemory(db_path=temp_chroma_db)
        now = datetime.now(timezone.utc)
        
        events = [
            {"id": "s1", "cat": "supply", "score": 4, "date": now.strftime('%Y-%m-%d')},
            {"id": "s2", "cat": "supply", "score": 2, "date": (now - timedelta(hours=10)).strftime('%Y-%m-%d')},
            {"id": "d1", "cat": "demand", "score": -3, "date": (now - timedelta(hours=5)).strftime('%Y-%m-%d')},
            {"id": "old1", "cat": "geopolitics", "score": 5, "date": (now - timedelta(days=2)).strftime('%Y-%m-%d')},
        ]

        for event in events:
            article_data = {
                "article": {"id": event["id"], "title": "T", "url": "U", "published_at": event["date"] + "T00:00:00Z", "data_source": "d", "description": None, "source": None, "content_snippet": None},
                "is_relevant": True, "category": event["cat"], "impact_score": event["score"], "impact_summary": "s", "confidence": 1.0, "classified_at": "t"
            }
            await memory.store_event(article_data, {})
        
        import time; await asyncio.sleep(0.5)

        # --- 2. Call API ---
        with patch('app.api.news.MarketMemory', return_value=memory):
            response = client.get("/api/news/factors/summary")
            assert response.status_code == 200
            summary = response.json()

        # --- 3. Assert ---
        assert len(summary['factors']) == 2 # supply and demand, geopolitics is too old
        
        supply_factor = next(f for f in summary['factors'] if f['category'] == 'supply')
        demand_factor = next(f for f in summary['factors'] if f['category'] == 'demand')

        assert supply_factor['article_count'] == 2
        assert supply_factor['avg_score'] == 3.0
        assert supply_factor['trend'] == 'bullish'

        assert demand_factor['article_count'] == 1
        assert demand_factor['avg_score'] == -3.0
        assert demand_factor['trend'] == 'bearish'

        assert summary['overall_sentiment'] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_similar_event_relevance(self, client, temp_chroma_db):
        """유사 사례 검색 결과가 쿼리와 관련성이 있는지 확인"""
        # --- 1. Setup: Manually populate DB ---
        memory = MarketMemory(db_path=temp_chroma_db)
        
        event_opec = {
            "article": {"id": "opec1", "title": "OPEC+ maintains oil production cuts", "url": "U", "published_at": "d", "data_source": "d", "description": None, "source": None, "content_snippet": None},
            "is_relevant": True, "category": "supply", "impact_score": 2, "impact_summary": "OPEC+가 감산을 유지하기로 결정했습니다.", "confidence": 1.0, "classified_at": "t"
        }
        event_fed = {
            "article": {"id": "fed1", "title": "US Federal Reserve hints at interest rate stability", "url": "U", "published_at": "d", "data_source": "d", "description": None, "source": None, "content_snippet": None},
            "is_relevant": True, "category": "macro", "impact_score": 1, "impact_summary": "미 연준이 금리 안정을 시사했습니다.", "confidence": 1.0, "classified_at": "t"
        }
        await memory.store_event(event_opec, {})
        await memory.store_event(event_fed, {})
        
        import time; await asyncio.sleep(0.5)

        # --- 2. Call API ---
        with patch('app.api.news.MarketMemory', return_value=memory):
            response_opec = client.get("/api/news/similar?query=OPEC oil production")
            assert response_opec.status_code == 200
            results_opec = response_opec.json()

            response_fed = client.get("/api/news/similar?query=US interest rates")
            assert response_fed.status_code == 200
            results_fed = response_fed.json()

        # --- 3. Assert ---
        assert len(results_opec) > 0
        assert results_opec[0]['title'] == "OPEC+ maintains oil production cuts"
        assert results_opec[0]['category'] == "supply"

        assert len(results_fed) > 0
        assert results_fed[0]['title'] == "US Federal Reserve hints at interest rate stability"
        assert results_fed[0]['category'] == "macro"
