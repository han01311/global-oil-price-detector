import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock, call

from app.services.historical_loader import HistoricalLoader
from app.schemas.price import PriceHistory, OilPrice
from app.services.market_memory import MarketMemory

@pytest.fixture
def mock_prices_df():
    """Provides a mock DataFrame of prices for testing."""
    dates = pd.to_datetime([datetime(2022, 3, 10) - timedelta(days=i) for i in range(40)])
    prices = pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'wti': [120 - i * 0.5 for i in range(40)],
        'brent': [125 - i * 0.5 for i in range(40)]
    })
    return prices.sort_values('date').reset_index(drop=True)

@pytest.fixture
def mock_price_history(mock_prices_df):
    """Provides a mock PriceHistory object."""
    prices = [OilPrice(**row) for __, row in mock_prices_df.iterrows()]
    return PriceHistory(prices=prices, source="eia", last_updated="2023-01-01T00:00:00Z")


@pytest.mark.asyncio
@patch('app.services.historical_loader.MarketMemory', autospec=True)
@patch('app.services.historical_loader.DataCollector', autospec=True)
async def test_load_seed_events_calls_dependencies(MockDataCollector, MockMarketMemory, mock_price_history):
    """Test that loader calls DataCollector and MarketMemory correctly."""
    # Arrange
    mock_collector_instance = MockDataCollector.return_value
    mock_collector_instance.collect_prices = AsyncMock(return_value=mock_price_history)
    
    mock_memory_instance = MockMarketMemory.return_value
    mock_memory_instance.is_available.return_value = True
    mock_memory_instance.store_event = AsyncMock()

    loader = HistoricalLoader()
    # Use a smaller list for testing
    loader.SEED_EVENTS = [
        {
            "date": "2022-02-24",
            "title": "Russia Invades Ukraine",
            "summary": "...",
            "category": "geopolitics",
            "impact_score": 5,
        }
    ]

    # Act
    await loader.load_seed_events()

    # Assert
    mock_collector_instance.collect_prices.assert_awaited_once()
    mock_memory_instance.store_event.assert_awaited_once()

    # Check the arguments passed to store_event
    args, kwargs = mock_memory_instance.store_event.call_args
    classified_article = args[0]
    price_changes = args[1]

    assert classified_article['article']['title'] == "Russia Invades Ukraine"
    assert classified_article['category'] == 'geopolitics'
    assert classified_article['confidence'] == 1.0
    assert 'wti_change_7d' in price_changes
    assert price_changes['wti_change_7d'] is not None


@pytest.mark.asyncio
@patch('app.services.historical_loader.DataCollector', autospec=True)
async def test_loader_integration_with_chromadb(MockDataCollector, mock_price_history, tmp_path):
    """Test the full flow of loading data into a real (temporary) ChromaDB."""
    # Arrange
    db_path = str(tmp_path / "chromadb_test_loader")
    
    # Mock the data collector
    mock_collector_instance = MockDataCollector.return_value
    mock_collector_instance.collect_prices = AsyncMock(return_value=mock_price_history)

    # Use a real MarketMemory instance with a temp path
    with patch('app.services.historical_loader.MarketMemory', lambda: MarketMemory(db_path=db_path)):
        loader = HistoricalLoader()
        # Use a small, distinct set of events for this test
        loader.SEED_EVENTS = [
            {"date": "2022-02-24", "title": "War Begins", "summary": "...", "category": "geopolitics", "impact_score": 5},
            {"date": "2022-03-01", "title": "Sanctions Imposed", "summary": "...", "category": "geopolitics", "impact_score": 4},
            {"date": "2022-03-05", "title": "Oil Prices Soar", "summary": "...", "category": "supply", "impact_score": 3},
        ]

        # Act
        await loader.load_seed_events()

    # Assert
    # Now, create a new MarketMemory instance pointing to the same DB and check its contents
    memory_checker = MarketMemory(db_path=db_path)
    assert memory_checker.is_available()
    
    # AC 1 & 2: Check if events are loaded with price data
    # The count is based on the number of documents in the collection
    collection_count = memory_checker._collection.count()
    assert collection_count == 3

    # AC 3: Check if search works
    search_results = await memory_checker.search_similar("impact of war on oil", n_results=2)
    assert len(search_results) == 2
    assert search_results[0]['metadata']['category'] == 'geopolitics'
    assert 'wti_change_1d' in search_results[0]['metadata']
    assert search_results[0]['metadata']['wti_change_1d'] is not None

    # AC 4: Check category distribution
    stats = await memory_checker.get_category_stats()
    assert stats['geopolitics']['count'] == 2
    assert stats['supply']['count'] == 1
    assert stats['geopolitics']['average_impact'] == (5 + 4) / 2
