"""
뉴스 데이터 수집기 테스트
"""
import pytest
import respx
from httpx import Response
from datetime import datetime
from app.services.data_collector import NewsCollector, DataCollector

# Mock responses
MOCK_NEWSAPI_RESPONSE = {
    "status": "ok",
    "totalResults": 2,
    "articles": [
        {
            "source": {"id": "reuters", "name": "Reuters"},
            "author": "John Doe",
            "title": "Oil Prices Surge Amidst New Tensions",
            "description": "A detailed report on rising oil prices.",
            "url": "https://www.reuters.com/oil-prices-surge",
            "urlToImage": "...",
            "publishedAt": "2023-11-01T10:00:00Z",
            "content": "Crude oil prices jumped more than 2% on Wednesday..."
        },
        {
            "source": {"id": None, "name": "Bloomberg"},
            "author": "Jane Smith",
            "title": "OPEC+ Considers Production Cuts",
            "description": "OPEC+ is meeting next week.",
            "url": "https://www.bloomberg.com/opec-cuts",
            "urlToImage": "...",
            "publishedAt": "2023-11-01T09:00:00Z",
            "content": "Sources say that OPEC+ is leaning towards a cut..."
        }
    ]
}

MOCK_GDELT_RESPONSE = {
    "articles": [
        {
            "url": "https://www.some-energy-site.com/news-on-oil",
            "title": "Energy Sector Analysis: Oil and Gas",
            "domain": "some-energy-site.com",
            "seendate": "20231101120000",
            "socialimage": "..."
        },
        {  # This one is a duplicate of the newsapi one
            "url": "https://www.reuters.com/oil-prices-surge",
            "title": "Oil Prices Surge Amidst New Tensions",
            "domain": "reuters.com",
            "seendate": "20231101110000",
            "socialimage": "..."
        }
    ]
}


@pytest.fixture
def news_collector():
    return NewsCollector()


@pytest.mark.asyncio
@respx.mock
async def test_get_latest_news_success(news_collector, monkeypatch):
    monkeypatch.setattr("app.services.data_collector.settings.NEWS_API_KEY", "TEST_KEY")
    route = respx.get(url__regex=r".*newsapi.org.*").mock(return_value=Response(200, json=MOCK_NEWSAPI_RESPONSE))

    articles = await news_collector.get_latest_news()

    assert route.call_count == 1
    # Check if query is constructed correctly
    query_param = route.calls[0].request.url.params['q']
    assert '"crude oil"' in query_param
    assert ' OR ' in query_param
    assert '"oil reserves"' in query_param

    assert len(articles) == 2
    assert articles[0]['title'] == "Oil Prices Surge Amidst New Tensions"
    assert articles[0]['data_source'] == "newsapi"
    assert articles[0]['source'] == "Reuters"
    assert 'id' in articles[0]


@pytest.mark.asyncio
async def test_get_latest_news_no_key(news_collector, monkeypatch):
    monkeypatch.setattr("app.services.data_collector.settings.NEWS_API_KEY", None)
    articles = await news_collector.get_latest_news()
    assert articles == []


@pytest.mark.asyncio
@respx.mock
async def test_get_gdelt_events_success(news_collector):
    route = respx.get(url__regex=r".*gdeltproject.org.*", name="gdelt").mock(return_value=Response(200, json=MOCK_GDELT_RESPONSE))

    articles = await news_collector.get_gdelt_events("2023-11-01", "2023-11-01")

    assert route.call_count == 1
    assert len(articles) == 2
    assert articles[0]['title'] == "Energy Sector Analysis: Oil and Gas"
    assert articles[0]['data_source'] == "gdelt"
    assert articles[0]['published_at'] == "2023-11-01T12:00:00Z"  # Check ISO format


@pytest.mark.asyncio
@respx.mock
async def test_caching_logic(news_collector, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.data_collector.settings.NEWS_API_KEY", "TEST_KEY")
    news_collector.cache_dir = tmp_path

    route = respx.get(url__regex=r".*newsapi.org.*").mock(return_value=Response(200, json=MOCK_NEWSAPI_RESPONSE))

    # First call
    await news_collector.get_latest_news()
    assert route.call_count == 1
    today = datetime.now().strftime('%Y-%m-%d')
    assert (tmp_path / f"{today}_newsapi.json").exists()

    # Second call
    await news_collector.get_latest_news()
    assert route.call_count == 1  # No new call


@pytest.mark.asyncio
@respx.mock
async def test_data_collector_collect_news_deduplication(monkeypatch):
    monkeypatch.setattr("app.services.data_collector.settings.NEWS_API_KEY", "TEST_KEY")

    respx.get(url__regex=r".*newsapi.org.*", name="newsapi").mock(return_value=Response(200, json=MOCK_NEWSAPI_RESPONSE))
    respx.get(url__regex=r".*gdeltproject.org.*", name="gdelt").mock(return_value=Response(200, json=MOCK_GDELT_RESPONSE))

    collector = DataCollector()
    articles = await collector.collect_news()

    # Total articles = 2 (newsapi) + 2 (gdelt) = 4. One is duplicate.
    assert len(articles) == 3

    urls = [a['url'] for a in articles]
    assert len(urls) == len(set(urls))  # Check for uniqueness

    # Check that we have articles from both sources
    sources = {a['data_source'] for a in articles}
    assert "newsapi" in sources
    assert "gdelt" in sources
