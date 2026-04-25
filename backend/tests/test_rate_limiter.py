"""
Rate Limiter 단위 테스트
"""
from __future__ import annotations

import pytest
import pytest_asyncio
import asyncio
import os
import time
from unittest.mock import patch, AsyncMock

# Set test environment before imports
os.environ["EIA_API_KEY"] = "test_key"
os.environ["FRED_API_KEY"] = "test_key"
os.environ["DATABASE_PATH"] = "data/test_rate_limiter.db"


@pytest_asyncio.fixture(autouse=True)
async def setup_and_teardown():
    """각 테스트 전후로 DB 초기화"""
    from app.core.database import Database
    from app.services.rate_limiter import RateLimiter

    # Reset singletons
    Database._instance = None
    Database._db = None
    RateLimiter._instance = None

    db = Database()
    await db.connect()
    yield
    await db.close()

    # Cleanup
    db_path = "data/test_rate_limiter.db"
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.mark.asyncio
async def test_rate_limiter_acquire_unlimited():
    """무제한 API(EIA)에 대해 항상 True를 반환해야 한다."""
    from app.services.rate_limiter import RateLimiter

    limiter = RateLimiter()
    result = await limiter.acquire("eia")
    assert result is True


@pytest.mark.asyncio
async def test_rate_limiter_acquire_limited_under_quota():
    """일일 한도 미달 시 True를 반환해야 한다."""
    from app.services.rate_limiter import RateLimiter

    limiter = RateLimiter()
    result = await limiter.acquire("newsapi")
    assert result is True


@pytest.mark.asyncio
async def test_rate_limiter_acquire_limited_over_quota():
    """일일 한도 초과 시 False를 반환해야 한다."""
    from app.services.rate_limiter import RateLimiter
    from app.core.database import Database

    db = Database()

    # 카운터를 100(최대)까지 인위적으로 채움
    conn = await db.get_conn()
    from datetime import datetime
    today = datetime.utcnow().strftime("%Y-%m-%d")
    await conn.execute(
        "INSERT OR REPLACE INTO rate_limit_counters (source, date, request_count, last_request_at) "
        "VALUES (?, ?, ?, ?)",
        ("newsapi", today, 100, datetime.utcnow().isoformat()),
    )
    await conn.commit()

    limiter = RateLimiter()
    result = await limiter.acquire("newsapi")
    assert result is False


@pytest.mark.asyncio
async def test_rate_limiter_counter_increments():
    """호출마다 카운터가 증가해야 한다."""
    from app.services.rate_limiter import RateLimiter

    limiter = RateLimiter()
    await limiter.acquire("gnews")
    await limiter.acquire("gnews")

    status = await limiter.get_remaining("gnews")
    assert status["used"] == 2


@pytest.mark.asyncio
async def test_rate_limiter_get_all_status():
    """모든 소스의 상태를 반환해야 한다."""
    from app.services.rate_limiter import RateLimiter

    limiter = RateLimiter()
    all_status = await limiter.get_all_status()
    source_names = [s["source"] for s in all_status]
    assert "eia" in source_names
    assert "fred" in source_names
    assert "newsapi" in source_names
    assert "gnews" in source_names
    assert "gdelt" in source_names


@pytest.mark.asyncio
async def test_rate_limiter_unknown_source():
    """알 수 없는 소스에 대해 True를 반환해야 한다."""
    from app.services.rate_limiter import RateLimiter

    limiter = RateLimiter()
    result = await limiter.acquire("unknown_source")
    assert result is True


@pytest.mark.asyncio
async def test_backoff_retries_on_error():
    """with_backoff이 재시도 가능한 에러에서 재시도해야 한다."""
    from app.services.rate_limiter import with_backoff

    call_count = 0

    async def failing_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("HTTP 429 Too Many Requests")
        return "success"

    result = await with_backoff("eia", failing_func)
    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_backoff_raises_on_non_retryable():
    """with_backoff이 재시도 불가한 에러는 즉시 raise해야 한다."""
    from app.services.rate_limiter import with_backoff

    async def failing_func():
        raise ValueError("Invalid data format")

    with pytest.raises(ValueError):
        await with_backoff("eia", failing_func)
