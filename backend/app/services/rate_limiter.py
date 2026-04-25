from __future__ import annotations

"""
API별 Rate Limit 관리 모듈
각 외부 API의 무료 정책을 준수하기 위한 중앙 제어 엔진.

정책 요약:
- EIA:     무제한 (초당 1요청 권장) → 1.5초 딜레이
- FRED:    무제한 (합리적 사용)    → 2.0초 딜레이
- NewsAPI: 100회/일               → 일일 카운터 + 1초 딜레이
- GNews:   100회/일, 10건/요청    → 일일 카운터 + 1초 딜레이
- GDELT:   동적 (5-6초 간격)      → 6초 딜레이
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime

from app.core.database import Database

logger = logging.getLogger(__name__)


@dataclass
class RateLimitPolicy:
    """API Rate Limit 정책 정의"""
    name: str
    max_requests_per_day: int | None  # None = 무제한
    min_interval_seconds: float       # 요청 간 최소 간격
    max_retries: int = 3
    backoff_base: float = 2.0         # Exponential backoff 베이스


# ──────────────────────────────────────────────
# 각 API별 정책 레지스트리
# ──────────────────────────────────────────────
POLICIES: dict[str, RateLimitPolicy] = {
    "eia": RateLimitPolicy(
        name="eia",
        max_requests_per_day=None,
        min_interval_seconds=1.5,
    ),
    "fred": RateLimitPolicy(
        name="fred",
        max_requests_per_day=None,
        min_interval_seconds=2.0,
    ),
    "newsapi": RateLimitPolicy(
        name="newsapi",
        max_requests_per_day=100,
        min_interval_seconds=1.0,
    ),
    "gnews": RateLimitPolicy(
        name="gnews",
        max_requests_per_day=100,
        min_interval_seconds=1.0,
    ),
    "gdelt": RateLimitPolicy(
        name="gdelt",
        max_requests_per_day=None,
        min_interval_seconds=6.0,
    ),
}


class RateLimiter:
    """
    API Rate Limit을 중앙 관리하는 비동기 엔진.

    사용법:
        limiter = RateLimiter()
        can_proceed = await limiter.acquire("newsapi")
        if can_proceed:
            # API 호출
        else:
            # 일일 한도 초과 → 건너뛰기
    """

    _instance: "RateLimiter | None" = None
    _last_request_time: dict[str, float]

    def __new__(cls) -> "RateLimiter":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._last_request_time = {}
        return cls._instance

    async def acquire(self, source: str) -> bool:
        """
        Rate Limit 체크 및 요청 허가.

        - 일일 한도가 있는 API: 카운터 확인 → 초과 시 False 반환
        - 최소 간격: 필요시 asyncio.sleep으로 대기
        - DB에 카운터 기록

        Returns:
            True: 요청 가능
            False: 일일 한도 초과 (건너뛰어야 함)
        """
        policy = POLICIES.get(source)
        if not policy:
            logger.warning(f"Unknown rate limit policy for source: {source}")
            return True

        # 1. 일일 한도 확인
        if policy.max_requests_per_day is not None:
            db = Database()
            counter = await db.get_rate_counter(source)
            current_count = counter["request_count"]

            if current_count >= policy.max_requests_per_day:
                logger.warning(
                    f"[RateLimiter] {source}: 일일 한도 초과 "
                    f"({current_count}/{policy.max_requests_per_day}). 건너뜁니다."
                )
                return False

        # 2. 최소 간격 대기
        now = time.monotonic()
        last_time = self._last_request_time.get(source, 0)
        elapsed = now - last_time
        wait_time = policy.min_interval_seconds - elapsed

        if wait_time > 0:
            logger.debug(f"[RateLimiter] {source}: {wait_time:.1f}초 대기 중...")
            await asyncio.sleep(wait_time)

        # 3. 카운터 증가 + 시각 기록
        self._last_request_time[source] = time.monotonic()

        if policy.max_requests_per_day is not None:
            db = Database()
            new_count = await db.increment_rate_counter(source)
            logger.info(
                f"[RateLimiter] {source}: 요청 #{new_count}/{policy.max_requests_per_day}"
            )
        else:
            # 무제한 API도 카운터는 기록 (통계용)
            db = Database()
            await db.increment_rate_counter(source)

        return True

    async def get_remaining(self, source: str) -> dict:
        """특정 소스의 잔여 요청 수 조회"""
        policy = POLICIES.get(source)
        if not policy:
            return {"source": source, "remaining": -1, "limit": None}

        db = Database()
        counter = await db.get_rate_counter(source)
        current_count = counter["request_count"]

        if policy.max_requests_per_day is None:
            return {
                "source": source,
                "used": current_count,
                "limit": None,
                "remaining": None,
                "last_request_at": counter["last_request_at"],
            }

        return {
            "source": source,
            "used": current_count,
            "limit": policy.max_requests_per_day,
            "remaining": max(0, policy.max_requests_per_day - current_count),
            "last_request_at": counter["last_request_at"],
        }

    async def get_all_status(self) -> list[dict]:
        """모든 소스의 Rate Limit 현황"""
        results = []
        for source in POLICIES:
            status = await self.get_remaining(source)
            status["min_interval_seconds"] = POLICIES[source].min_interval_seconds
            results.append(status)
        return results

    def get_policy(self, source: str) -> RateLimitPolicy | None:
        """정책 조회"""
        return POLICIES.get(source)


async def with_backoff(source: str, func, *args, **kwargs):
    """
    Exponential Backoff로 함수를 재시도.

    HTTP 429/500 등 에러 시 최대 max_retries까지 지수적으로 대기 후 재시도.

    Args:
        source: Rate limit 정책 이름
        func: 호출할 비동기 함수
        *args, **kwargs: 함수 인자

    Returns:
        함수 실행 결과

    Raises:
        마지막 재시도도 실패하면 원래 예외를 다시 raise
    """
    policy = POLICIES.get(source, RateLimitPolicy(name=source, max_requests_per_day=None, min_interval_seconds=1.0))

    last_error = None
    for attempt in range(1, policy.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_error = e
            error_msg = str(e)

            # 429 (Too Many Requests) 또는 서버 에러는 재시도 대상
            is_retryable = any(code in error_msg for code in ["429", "500", "502", "503", "504", "rate", "Rate"])

            if not is_retryable or attempt == policy.max_retries:
                logger.error(
                    f"[Backoff] {source}: 최종 실패 (시도 {attempt}/{policy.max_retries}): {e}"
                )
                raise

            wait_time = policy.backoff_base ** attempt
            logger.warning(
                f"[Backoff] {source}: 재시도 {attempt}/{policy.max_retries}, "
                f"{wait_time:.1f}초 대기 (에러: {error_msg[:100]})"
            )
            await asyncio.sleep(wait_time)

    raise last_error  # type: ignore
