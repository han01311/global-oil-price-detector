import pytest
import pandas as pd
from datetime import datetime, timedelta

from app.services.market_memory import MarketMemory
from app.utils.price_utils import calculate_price_changes

# --- Fixtures ---

@pytest.fixture
def memory_instance(tmp_path):
    """Provides a MarketMemory instance with a temporary DB path."""
    db_path = str(tmp_path / "chromadb_test")
    memory = MarketMemory(db_path=db_path)
    # Clean up collection before test
    if memory.is_available():
        memory._client.delete_collection(name=memory.COLLECTION_NAME)
        memory._collection = memory._client.get_or_create_collection(
            name=memory.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
    return memory

@pytest.fixture
def sample_classified_article_1():
    return {
        "article": {
            "id": "test-id-1", "title": "OPEC+ Agrees to Deepen Oil Production Cuts",
            "description": "The group decided to cut production.", "source": "Reuters",
            "url": "http://example.com/opec-cuts", "published_at": "2024-07-15T12:00:00Z",
            "content_snippet": "...", "data_source": "newsapi"
        },
        "is_relevant": True, "category": "supply", "sub_categories": [],
        "impact_score": 4, "impact_summary": "OPEC+의 감산은 공급 감소로 유가 상승 요인입니다.",
        "confidence": 0.95, "classified_at": "2024-07-16T10:00:00Z"
    }

@pytest.fixture
def sample_classified_article_2():
    return {
        "article": {
            "id": "test-id-2", "title": "Global Recession Fears Mount, Hurting Oil Demand",
            "description": "Economic slowdown concerns are growing.", "source": "Bloomberg",
            "url": "http://example.com/recession-fears", "published_at": "2024-07-10T12:00:00Z",
            "content_snippet": "...", "data_source": "newsapi"
        },
        "is_relevant": True, "category": "demand", "sub_categories": ["macro"],
        "impact_score": -3, "impact_summary": "경기 침체 우려는 수요 감소로 유가 하락 요인입니다.",
        "confidence": 0.90, "classified_at": "2024-07-11T10:00:00Z"
    }

@pytest.fixture
def sample_price_changes():
    return {
        "wti_change_1d": 1.5, "wti_change_7d": 3.2, "wti_change_30d": 5.0,
        "brent_change_1d": 1.4, "brent_change_7d": 3.1, "brent_change_30d": 4.8,
    }

@pytest.fixture
def sample_prices_df():
    dates = pd.to_datetime([datetime(2024, 7, 15) - timedelta(days=i) for i in range(40)])
    prices = pd.DataFrame({
        'date': dates,
        'wti': [100 - i * 0.1 for i in range(40)],
        'brent': [105 - i * 0.1 for i in range(40)]
    })
    return prices.sort_values('date').reset_index(drop=True)


# --- Tests for price_utils.py ---

def test_calculate_price_changes_correctly(sample_prices_df):
    """Test that price changes are calculated accurately."""
    event_date = "2024-07-15"
    
    changes = calculate_price_changes(sample_prices_df, event_date)
    
    assert changes is not None
    # WTI: (100.0 - 99.9) / 99.9 * 100 = 0.1001
    assert pytest.approx(changes["wti_change_1d"], abs=1e-4) == 0.1001
    # WTI: (100.0 - 99.3) / 99.3 * 100 = 0.7049
    assert pytest.approx(changes["wti_change_7d"], abs=1e-4) == 0.7049
    # WTI: (100.0 - 97.0) / 97.0 * 100 = 3.0927
    assert pytest.approx(changes["wti_change_30d"], abs=1e-4) == 3.0927
    # Brent: (105.0 - 104.9) / 104.9 * 100 = 0.0953
    assert pytest.approx(changes["brent_change_1d"], abs=1e-4) == 0.0953


def test_calculate_price_changes_with_missing_dates(sample_prices_df):
    """Test calculation when exact past dates are missing."""
    # Drop the date for 7 days ago
    df = sample_prices_df.drop(sample_prices_df[sample_prices_df['date'] == pd.to_datetime('2024-07-08')].index)
    
    changes = calculate_price_changes(df, "2024-07-15")
    
    # It should use the nearest date (2024-07-07), where price is 99.2
    # 7d change: (100.0 - 99.2) / 99.2 * 100 = 0.8064
    assert pytest.approx(changes["wti_change_7d"], abs=1e-4) == 0.8064


# --- Tests for market_memory.py ---

@pytest.mark.asyncio
async def test_store_and_search_event(memory_instance, sample_classified_article_1, sample_price_changes):
    """AC 1 & 2: Test storing an event and searching for it."""
    assert memory_instance.is_available()
    
    await memory_instance.store_event(sample_classified_article_1, sample_price_changes)
    
    # Wait a bit for chromadb to process
    import time; time.sleep(0.5)

    query = "What did OPEC+ decide about oil production?"
    results = await memory_instance.search_similar(query, n_results=1)
    
    assert len(results) == 1
    result = results[0]
    assert result['id'] == "test-id-1"
    assert "OPEC+" in result['document']
    assert result['metadata']['category'] == "supply"
    assert result['metadata']['impact_score'] == 4
    assert result['metadata']['wti_change_7d'] == 3.2

@pytest.mark.asyncio
async def test_search_with_category_filter(memory_instance, sample_classified_article_1, sample_classified_article_2, sample_price_changes):
    """AC 3: Test that category filtering works correctly."""
    await memory_instance.store_event(sample_classified_article_1, sample_price_changes)
    await memory_instance.store_event(sample_classified_article_2, sample_price_changes)
    
    import time; time.sleep(0.5)

    # Search with a general query but filter by category 'demand'
    query = "news about oil market"
    results = await memory_instance.search_similar(query, category="demand", n_results=5)
    
    assert len(results) == 1
    assert results[0]['id'] == "test-id-2"
    assert results[0]['metadata']['category'] == "demand"

@pytest.mark.asyncio
async def test_search_returns_sorted_results(memory_instance, sample_classified_article_1, sample_classified_article_2, sample_price_changes):
    """AC 3 (cont.): Test that results are sorted by similarity."""
    # Article 2 is intentionally less similar to the query
    await memory_instance.store_event(sample_classified_article_1, sample_price_changes)
    await memory_instance.store_event(sample_classified_article_2, sample_price_changes)
    
    import time; time.sleep(0.5)

    query = "OPEC production cuts" # Very similar to article 1
    results = await memory_instance.search_similar(query, n_results=2)
    
    assert len(results) == 2
    # The first result should be article 1, with a smaller distance
    assert results[0]['id'] == "test-id-1"
    assert results[1]['id'] == "test-id-2"
    assert results[0]['distance'] < results[1]['distance']

@pytest.mark.asyncio
async def test_get_category_stats(memory_instance, sample_classified_article_1, sample_classified_article_2, sample_price_changes):
    """Test that category statistics are calculated correctly."""
    await memory_instance.store_event(sample_classified_article_1, sample_price_changes)
    await memory_instance.store_event(sample_classified_article_2, sample_price_changes)
    
    # Add another 'supply' event
    article_3 = sample_classified_article_1.copy()
    article_3['article'] = article_3['article'].copy()
    article_3['article']['id'] = 'test-id-3'
    article_3['impact_score'] = 2
    await memory_instance.store_event(article_3, sample_price_changes)
    
    import time; time.sleep(0.5)

    stats = await memory_instance.get_category_stats()
    
    assert "supply" in stats
    assert "demand" in stats
    assert stats['supply']['count'] == 2
    assert stats['demand']['count'] == 1
    assert stats['supply']['average_impact'] == (4 + 2) / 2  # 3.0
    assert stats['demand']['average_impact'] == -3.0
