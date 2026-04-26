"""
NYT & Guardian 과거 기사 크롤러 (2000~현재)
연도별로 순차 수집하여 SQLite DB에 저장.

사용법:
    python3 scripts/crawl_history.py                  # 전체 실행
    python3 scripts/crawl_history.py --start 2010     # 2010년부터 재개
    python3 scripts/crawl_history.py --stop           # 진행 상태 파일 삭제 (초기화)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from hashlib import sha256
from typing import List, Dict, Any

import httpx

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.database import Database
from app.services.rate_limiter import RateLimiter, with_backoff

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
START_YEAR = 2000
END_YEAR = datetime.now().year
TARGET_TOTAL = 2000  # 목표 총 기사 수

STATE_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "history_crawl_state.json"
)

# ──────────────────────────────────────────────
# 진행 상태 관리
# ──────────────────────────────────────────────
def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"last_completed_year": None, "total_collected": 0}

def save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def clear_state():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
        logger.info("크롤링 상태 파일이 초기화되었습니다.")
    else:
        logger.info("초기화할 상태 파일이 없습니다.")


# ──────────────────────────────────────────────
# API 클라이언트
# ──────────────────────────────────────────────
async def fetch_nyt_year(year: int, target_count: int, rate_limiter: RateLimiter) -> List[Dict[str, Any]]:
    articles = []
    if not settings.NYT_API_KEY:
        logger.warning("NYT_API_KEY가 없습니다.")
        return articles

    begin_date = f"{year}0101"
    end_date = f"{year}1231"
    query = '("crude oil" OR "oil price" OR "OPEC")'
    
    # 1페이지당 10개
    max_pages = max(target_count // 10 + 1, 1)
    
    for page in range(max_pages):
        can_proceed = await rate_limiter.acquire("nyt")
        if not can_proceed:
            logger.warning("NYT 일일 한도 초과")
            break

        params = {
            "q": query,
            "begin_date": begin_date,
            "end_date": end_date,
            "sort": "newest",
            "page": page,
            "api-key": settings.NYT_API_KEY
        }

        async def do_fetch():
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get("https://api.nytimes.com/svc/search/v2/articlesearch.json", params=params)
                response.raise_for_status()
                return response.json()

        try:
            data = await with_backoff("nyt", do_fetch)
            docs = data.get("response", {}).get("docs", [])
            if not docs:
                break
                
            for doc in docs:
                title = doc.get('headline', {}).get('main', '')
                description = doc.get('abstract', '') or doc.get('snippet', '')
                pub_date = doc.get('pub_date', f"{year}-01-01T00:00:00Z")
                link = doc.get('web_url', '')
                
                if link:
                    articles.append({
                        "id": sha256(link.encode()).hexdigest(),
                        "title": title, 
                        "description": description,
                        "source": "New York Times", 
                        "url": link,
                        "published_at": pub_date, 
                        "content_snippet": description[:200] if description else None,
                        "data_source": "nyt"
                    })
            
            logger.debug(f"[NYT] {year}년 page={page} 수집 완료 ({len(docs)}건)")
            if len(articles) >= target_count:
                break
        except Exception as e:
            logger.error(f"NYT {year}년 page={page} 실패: {e}")
            break

    return articles[:target_count]


async def fetch_guardian_year(year: int, target_count: int, rate_limiter: RateLimiter) -> List[Dict[str, Any]]:
    articles = []
    if not settings.GUARDIAN_API_KEY:
        logger.warning("GUARDIAN_API_KEY가 없습니다.")
        return articles

    from_date = f"{year}-01-01"
    to_date = f"{year}-12-31"
    query = '"crude oil" OR "oil price" OR OPEC'
    
    # Guardian은 페이지 사이즈를 50으로 설정
    page_size = min(target_count, 50)
    max_pages = max(target_count // page_size + 1, 1)

    import html
    import re
    def clean_html(raw_html):
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', raw_html)
        return html.unescape(cleantext)

    for page in range(1, max_pages + 1):
        can_proceed = await rate_limiter.acquire("guardian")
        if not can_proceed:
            logger.warning("Guardian 일일 한도 초과")
            break

        params = {
            "q": query,
            "from-date": from_date,
            "to-date": to_date,
            "order-by": "newest",
            "show-fields": "trailText",
            "page": page,
            "page-size": page_size,
            "api-key": settings.GUARDIAN_API_KEY
        }

        async def do_fetch():
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get("https://content.guardianapis.com/search", params=params)
                response.raise_for_status()
                return response.json()

        try:
            data = await with_backoff("guardian", do_fetch)
            results = data.get("response", {}).get("results", [])
            if not results:
                break

            for res in results:
                title = res.get('webTitle', '')
                description = clean_html(res.get('fields', {}).get('trailText', ''))
                pub_date = res.get('webPublicationDate', f"{year}-01-01T00:00:00Z")
                link = res.get('webUrl', '')

                if link:
                    articles.append({
                        "id": sha256(link.encode()).hexdigest(),
                        "title": title, 
                        "description": description,
                        "source": "The Guardian", 
                        "url": link,
                        "published_at": pub_date, 
                        "content_snippet": description[:200] if description else None,
                        "data_source": "guardian"
                    })
                    
            logger.debug(f"[Guardian] {year}년 page={page} 수집 완료 ({len(results)}건)")
            if len(articles) >= target_count:
                break
        except Exception as e:
            logger.error(f"Guardian {year}년 page={page} 실패: {e}")
            break
            
    return articles[:target_count]


async def crawl_all(start_year_override: int | None = None):
    db = Database()
    await db.connect()
    rate_limiter = RateLimiter()

    state = load_state()
    total_collected = state["total_collected"]
    last_year = state["last_completed_year"]

    if start_year_override is not None:
        first_year = start_year_override
    elif last_year is not None:
        first_year = last_year + 1
    else:
        first_year = START_YEAR

    years = list(range(first_year, END_YEAR + 1))
    num_years = len(years)

    if num_years == 0:
        logger.info("✅ 모든 연도 크롤링이 이미 완료되었습니다.")
        await db.close()
        return

    # 연도당 수집 목표 (NYT 60%, Guardian 40%)
    remaining = max(TARGET_TOTAL - total_collected, 0)
    per_year = max(remaining // num_years, 10) if num_years > 0 else 10
    
    nyt_per_year = int(per_year * 0.6)
    guardian_per_year = per_year - nyt_per_year

    logger.info(f"🚀 크롤링 시작: {first_year}~{END_YEAR} ({num_years}개 연도)")
    logger.info(f"   현재까지 수집: {total_collected}건 / 목표: {TARGET_TOTAL}건")
    logger.info(f"   연도당 목표: {per_year}건 (NYT: {nyt_per_year}, Guardian: {guardian_per_year})")

    for year in years:
        if total_collected >= TARGET_TOTAL:
            logger.info(f"🎯 목표 {TARGET_TOTAL}건 달성! 크롤링을 종료합니다.")
            break

        nyt_articles = await fetch_nyt_year(year, nyt_per_year, rate_limiter)
        guardian_articles = await fetch_guardian_year(year, guardian_per_year, rate_limiter)
        
        all_articles = nyt_articles + guardian_articles
        
        if all_articles:
            # 중복 제거 (URL 기준)
            unique_articles = []
            seen = set()
            for a in all_articles:
                if a["url"] not in seen:
                    unique_articles.append(a)
                    seen.add(a["url"])
            
            await db.upsert_news_articles(unique_articles)
            total_collected += len(unique_articles)
            logger.info(
                f"📰 {year}년: {len(unique_articles)}건 수집 완료 "
                f"(누적 {total_collected}/{TARGET_TOTAL})"
            )
        else:
            logger.warning(f"⚠️  {year}년: 수집된 기사 없음")

        state["last_completed_year"] = year
        state["total_collected"] = total_collected
        save_state(state)

    logger.info(f"✅ 크롤링 완료! 총 {total_collected}건 수집됨.")
    await db.close()


def main():
    global TARGET_TOTAL

    parser = argparse.ArgumentParser(description="NYT & Guardian 과거 기사 크롤러 (2000~현재)")
    parser.add_argument("--start", type=int, default=None, help="시작 연도")
    parser.add_argument("--stop", action="store_true", help="크롤링 상태 초기화")
    parser.add_argument("--target", type=int, default=2000, help="목표 수집 건수 (기본: 2000)")
    args = parser.parse_args()

    if args.stop:
        clear_state()
        return

    TARGET_TOTAL = args.target

    asyncio.run(crawl_all(start_year_override=args.start))


if __name__ == "__main__":
    main()
