"""
SQLite Database 단위 테스트
"""
from __future__ import annotations

import pytest
import pytest_asyncio
import os
from datetime import datetime

# Set test environment before imports
os.environ["EIA_API_KEY"] = "test_key"
os.environ["FRED_API_KEY"] = "test_key"
os.environ["DATABASE_PATH"] = "data/test_database.db"


@pytest_asyncio.fixture(autouse=True)
async def setup_and_teardown():
    """각 테스트 전후로 DB 초기화"""
    from app.core.database import Database

    Database._instance = None
    Database._db = None

    db = Database()
    await db.connect()
    yield db
    await db.close()

    db_path = "data/test_database.db"
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.mark.asyncio
async def test_db_connect():
    """DB 연결이 성공해야 한다."""
    from app.core.database import Database
    db = Database()
    conn = await db.get_conn()
    assert conn is not None


@pytest.mark.asyncio
async def test_upsert_oil_prices():
    """유가 데이터 upsert가 정상 동작해야 한다."""
    from app.core.database import Database
    db = Database()

    rows = [
        {"date": "2024-01-01", "wti": 70.5, "brent": 75.3},
        {"date": "2024-01-02", "wti": 71.0, "brent": 76.0},
    ]
    count = await db.upsert_oil_prices(rows)
    assert count == 2

    # 조회 확인
    result = await db.get_oil_prices()
    assert len(result) == 2

    # 중복 upsert (같은 날짜)
    count2 = await db.upsert_oil_prices([{"date": "2024-01-01", "wti": 71.0, "brent": 76.0}])
    assert count2 == 1

    result2 = await db.get_oil_prices()
    assert len(result2) == 2  # 여전히 2건 (upsert)


@pytest.mark.asyncio
async def test_upsert_macro_indicators():
    """거시경제 지표 upsert가 정상 동작해야 한다."""
    from app.core.database import Database
    db = Database()

    rows = [
        {"date": "2024-01-01", "fed_rate": 5.33, "dollar_index": 103.5},
        {"date": "2024-01-02", "fed_rate": 5.33, "dollar_index": 103.2},
    ]
    count = await db.upsert_macro_indicators(rows)
    assert count == 2

    total = await db.get_macro_indicators_count()
    assert total == 2


@pytest.mark.asyncio
async def test_upsert_news_articles():
    """뉴스 기사 upsert가 정상 동작해야 한다."""
    from app.core.database import Database
    db = Database()

    articles = [
        {
            "id": "abc123",
            "title": "Oil prices surge amid tensions",
            "description": "Test desc",
            "source": "Reuters",
            "url": "https://example.com/1",
            "published_at": "2024-01-01T12:00:00Z",
            "content_snippet": "Oil prices...",
            "data_source": "newsapi",
        },
        {
            "id": "def456",
            "title": "OPEC announces production cut",
            "description": None,
            "source": "Bloomberg",
            "url": "https://example.com/2",
            "published_at": "2024-01-01T13:00:00Z",
            "content_snippet": None,
            "data_source": "gnews",
        },
    ]
    count = await db.upsert_news_articles(articles)
    assert count == 2

    total = await db.get_news_articles_count()
    assert total == 2

    # 소스별 필터
    newsapi_count = await db.get_news_articles_count(data_source="newsapi")
    assert newsapi_count == 1

    gnews_count = await db.get_news_articles_count(data_source="gnews")
    assert gnews_count == 1


@pytest.mark.asyncio
async def test_collection_log():
    """수집 로그 기록 및 조회가 정상 동작해야 한다."""
    from app.core.database import Database
    db = Database()

    log = {
        "source": "eia",
        "task_type": "prices",
        "status": "success",
        "records_count": 30,
        "error_message": None,
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": 1500,
    }
    log_id = await db.insert_collection_log(log)
    assert log_id > 0

    # 에러 로그도 추가
    error_log = {
        "source": "fred",
        "task_type": "macro",
        "status": "error",
        "records_count": 0,
        "error_message": "Connection timeout",
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": 5000,
    }
    await db.insert_collection_log(error_log)

    # 전체 조회
    logs = await db.get_collection_logs()
    assert len(logs) == 2

    # 소스 필터
    eia_logs = await db.get_collection_logs(source="eia")
    assert len(eia_logs) == 1

    # 상태 필터
    error_logs = await db.get_collection_logs(status="error")
    assert len(error_logs) == 1


@pytest.mark.asyncio
async def test_rate_limit_counter():
    """Rate limit 카운터가 정상 동작해야 한다."""
    from app.core.database import Database
    db = Database()

    c1 = await db.increment_rate_counter("newsapi")
    assert c1 == 1

    c2 = await db.increment_rate_counter("newsapi")
    assert c2 == 2

    counter = await db.get_rate_counter("newsapi")
    assert counter["request_count"] == 2
    assert counter["source"] == "newsapi"


@pytest.mark.asyncio
async def test_overview():
    """전체 현황 조회가 정상 동작해야 한다."""
    from app.core.database import Database
    db = Database()

    # 데이터 삽입
    await db.upsert_oil_prices([{"date": "2024-01-01", "wti": 70.0, "brent": 75.0}])
    await db.upsert_news_articles([{
        "id": "test1", "title": "Test", "url": "http://test.com",
        "published_at": "2024-01-01T12:00:00Z", "data_source": "newsapi",
    }])

    overview = await db.get_overview()
    assert overview["oil_prices"]["count"] >= 1
    assert overview["news_articles"]["count"] >= 1


@pytest.mark.asyncio
async def test_log_stats_by_source():
    """소스별 로그 통계가 정상 동작해야 한다."""
    from app.core.database import Database
    db = Database()

    # 다수 로그 삽입
    for i in range(3):
        await db.insert_collection_log({
            "source": "eia", "task_type": "prices", "status": "success",
            "records_count": 30, "started_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(), "duration_ms": 1000,
        })
    await db.insert_collection_log({
        "source": "eia", "task_type": "prices", "status": "error",
        "error_message": "timeout", "records_count": 0,
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": datetime.utcnow().isoformat(), "duration_ms": 5000,
    })

    stats = await db.get_log_stats_by_source()
    eia_stats = [s for s in stats if s["source"] == "eia"]
    assert len(eia_stats) == 1
    eia_stat = eia_stats[0]
    assert eia_stat["source"] == "eia"
    assert eia_stat["success_count"] >= 3
    assert eia_stat["error_count"] >= 1


@pytest.mark.asyncio
async def test_oil_inventory_and_production():
    """재고 및 생산량 데이터 upsert가 정상 동작해야 한다."""
    from app.core.database import Database
    db = Database()

    inv_rows = [{"date": "2024-01-05", "inventory_mbbl": 450000.5}]
    count = await db.upsert_oil_inventory(inv_rows)
    assert count == 1

    prod_rows = [{"date": "2024-01-05", "production_mbbl_d": 13200.0}]
    count2 = await db.upsert_oil_production(prod_rows)
    assert count2 == 1

    inv_count = await db.get_oil_inventory_count()
    assert inv_count == 1

    prod_count = await db.get_oil_production_count()
    assert prod_count == 1
