"""
NYT & Guardian 과거 기사 크롤러 (2000~현재)
연도별로 순차 수집하여 DB에 저장.

사용법:
    python3 scripts/crawl_history.py                              # 전체 실행
    python3 scripts/crawl_history.py --start 2010                 # 2010년부터 재개
    python3 scripts/crawl_history.py --start 2010 --end 2015      # 2010~2015 범위 수집
    python3 scripts/crawl_history.py --start 2020 --end 2020      # 2020년 단독 수집
    python3 scripts/crawl_history.py --stop                       # 진행 상태 파일 삭제 (초기화)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from hashlib import sha256
from typing import List, Dict, Any

import httpx

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.database import Database, get_session_factory
from sqlalchemy import select
from app.services.rate_limiter import RateLimiter, with_backoff

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
START_YEAR = 2000
END_YEAR = datetime.now().year
TARGET_TOTAL = 2000  # 목표 총 기사 수
END_YEAR_OVERRIDE = None  # --end 인자로 설정

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
async def fetch_nyt_year(year: int, target_count: int, existing_ids: set, rate_limiter: RateLimiter) -> tuple[List[Dict[str, Any]], str | None, int]:
    articles = []
    skipped_existing = 0
    if not settings.NYT_API_KEY:
        logger.warning("NYT_API_KEY가 없습니다.")
        return articles, "NYT_API_KEY가 없습니다.", skipped_existing

    begin_date = f"{year}0101"
    end_date = f"{year}1231"
    # 기존의 엄격한 exact match("crude oil")를 해제하고 넓게 검색하여 recall을 높임
    query = 'oil AND (price OR crude OR petroleum OR OPEC OR energy)'
    
    # NYT Search API는 최대 100페이지까지 허용됨
    max_pages = 100
    
    for page in range(max_pages):
        can_proceed = await rate_limiter.acquire("nyt")
        if not can_proceed:
            logger.warning("NYT 일일 한도 초과")
            return articles, "NYT 일일 한도 초과 (Rate Limit)", skipped_existing

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
                    article_id = sha256(link.encode()).hexdigest()
                    if article_id in existing_ids:
                        skipped_existing += 1
                        continue
                        
                    articles.append({
                        "id": article_id,
                        "title": title, 
                        "description": description,
                        "source": "New York Times", 
                        "url": link,
                        "published_at": pub_date, 
                        "content_snippet": description[:200] if description else None,
                        "data_source": "nyt"
                    })
            
            logger.debug(f"[NYT] {year}년 page={page} 수집 진행 (누적 신규 {len(articles)}건 / 목표 {target_count}건, 스킵 {skipped_existing}건)")
            if len(articles) >= target_count:
                break
        except Exception as e:
            logger.error(f"NYT {year}년 page={page} 실패: {e}")
            return articles, f"오류: {str(e)}", skipped_existing

    return articles[:target_count], None, skipped_existing


async def fetch_guardian_year(year: int, target_count: int, existing_ids: set, rate_limiter: RateLimiter) -> tuple[List[Dict[str, Any]], str | None, int]:
    articles = []
    skipped_existing = 0
    if not settings.GUARDIAN_API_KEY:
        logger.warning("GUARDIAN_API_KEY가 없습니다.")
        return articles, "GUARDIAN_API_KEY가 없습니다.", skipped_existing

    from_date = f"{year}-01-01"
    to_date = f"{year}-12-31"
    # Guardian API도 exact match("crude oil") 대신 넓은 키워드 사용
    query = 'oil AND (price OR crude OR petroleum OR OPEC OR energy)'
    
    # Guardian은 페이지 사이즈 50설정, 최대 100페이지
    page_size = min(max(target_count, 10), 50)
    max_pages = 100

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
            return articles, "Guardian 일일 한도 초과 (Rate Limit)", skipped_existing

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
                    article_id = sha256(link.encode()).hexdigest()
                    if article_id in existing_ids:
                        skipped_existing += 1
                        continue
                        
                    articles.append({
                        "id": article_id,
                        "title": title, 
                        "description": description,
                        "source": "The Guardian", 
                        "url": link,
                        "published_at": pub_date, 
                        "content_snippet": description[:200] if description else None,
                        "data_source": "guardian"
                    })
                    
            logger.debug(f"[Guardian] {year}년 page={page} 수집 진행 (누적 신규 {len(articles)}건 / 목표 {target_count}건, 스킵 {skipped_existing}건)")
            if len(articles) >= target_count:
                break
        except Exception as e:
            logger.error(f"Guardian {year}년 page={page} 실패: {e}")
            return articles, f"오류: {str(e)}", skipped_existing
            
    return articles[:target_count], None, skipped_existing


def emit_json(data: dict):
    """구조화된 JSON 라인을 stdout으로 출력 (API 서버에서 파싱용)"""
    print(json.dumps(data, ensure_ascii=False), flush=True)


async def crawl_all(start_year_override: int | None = None, end_year_override: int | None = None):
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

    # end_year: --end 인자가 있으면 해당 연도까지, 없으면 현재 연도까지
    final_year = end_year_override if end_year_override is not None else END_YEAR

    years = list(range(first_year, final_year + 1))
    num_years = len(years)

    if num_years == 0:
        emit_json({"type": "complete", "message": "모든 연도 크롤링이 이미 완료되었습니다.", "total_collected": total_collected})
        logger.info("✅ 모든 연도 크롤링이 이미 완료되었습니다.")
        await db.close()
        return

    # DB에서 기존 URL 해시셋 로드 (중복 방지용)
    existing_ids = await _load_existing_article_ids(db)
    logger.info(f"📦 DB 기존 기사: {len(existing_ids)}건 (URL 중복 필터 활성)")

    # 연도당 수집 목표 (NYT 60%, Guardian 40%)
    remaining = max(TARGET_TOTAL - total_collected, 0)
    per_year = max(remaining // num_years, 10) if num_years > 0 else 10
    
    nyt_per_year = int(per_year * 0.6)
    guardian_per_year = per_year - nyt_per_year

    crawl_start_time = time.time()

    # 연도별 수집 현황 추적 (실시간 프론트엔드 전송용)
    year_breakdown: List[Dict[str, Any]] = []

    emit_json({
        "type": "start",
        "year_start": first_year,
        "year_end": final_year,
        "years_total": num_years,
        "target": TARGET_TOTAL,
        "per_year": per_year,
        "nyt_per_year": nyt_per_year,
        "guardian_per_year": guardian_per_year,
        "existing_count": len(existing_ids),
    })
    logger.info(f"🚀 크롤링 시작: {first_year}~{final_year} ({num_years}개 연도)")
    logger.info(f"   현재까지 수집: {total_collected}건 / 목표: {TARGET_TOTAL}건")
    logger.info(f"   연도당 목표: {per_year}건 (NYT: {nyt_per_year}, Guardian: {guardian_per_year})")

    years_completed = 0
    total_nyt = 0
    total_guardian = 0
    total_dupes = 0
    total_skipped_existing = 0

    for year in years:
        if total_collected >= TARGET_TOTAL:
            emit_json({"type": "target_reached", "target": TARGET_TOTAL, "total_collected": total_collected})
            logger.info(f"🎯 목표 {TARGET_TOTAL}건 달성! 크롤링을 종료합니다.")
            break

        elapsed = time.time() - crawl_start_time

        # NYT 수집
        emit_json({"type": "progress", "year": year, "source": "nyt", "phase": "fetching", "elapsed_sec": round(elapsed)})
        nyt_articles, nyt_err, nyt_skipped = await fetch_nyt_year(year, nyt_per_year, existing_ids, rate_limiter)

        # Guardian 수집
        emit_json({"type": "progress", "year": year, "source": "guardian", "phase": "fetching", "elapsed_sec": round(time.time() - crawl_start_time)})
        guardian_articles, guardian_err, guardian_skipped = await fetch_guardian_year(year, guardian_per_year, existing_ids, rate_limiter)

        all_articles = nyt_articles + guardian_articles
        
        year_errors = []
        if nyt_err: year_errors.append(f"NYT: {nyt_err}")
        if guardian_err: year_errors.append(f"Guardian: {guardian_err}")
        error_str = " | ".join(year_errors) if year_errors else None
        
        skipped_existing = nyt_skipped + guardian_skipped
        total_skipped_existing += skipped_existing
        
        # 신규 기사가 없더라도 스킵된 기사가 있으면 로그를 남김
        if all_articles or skipped_existing > 0:
            # 중복 제거 1: 현재 배치 내 URL 중복 (동일 배치에서 중복되는 경우)
            unique_articles = []
            seen = set()
            for a in all_articles:
                if a["url"] not in seen:
                    unique_articles.append(a)
                    seen.add(a["url"])
            
            batch_dupes = len(all_articles) - len(unique_articles)
            total_dupes += batch_dupes

            new_articles = unique_articles
            nyt_new = len([a for a in new_articles if a["data_source"] == "nyt"])
            guardian_new = len([a for a in new_articles if a["data_source"] == "guardian"])
            total_nyt += nyt_new
            total_guardian += guardian_new

            if new_articles:
                saved = await db.upsert_news_articles(new_articles)
                for a in new_articles:
                    existing_ids.add(a["id"])
                total_collected += saved
            else:
                saved = 0

            years_completed += 1

            year_info = {
                "year": year,
                "nyt_fetched": len(nyt_articles),
                "guardian_fetched": len(guardian_articles),
                "nyt_new": nyt_new,
                "guardian_new": guardian_new,
                "saved": saved,
                "skipped_existing": skipped_existing,
                "dupes_in_batch": batch_dupes,
                "error": error_str,
            }
            year_breakdown.append(year_info)

            emit_json({
                "type": "year_done",
                "year": year,
                "nyt": nyt_new,
                "guardian": guardian_new,
                "nyt_fetched": len(nyt_articles),
                "guardian_fetched": len(guardian_articles),
                "saved": saved,
                "skipped_existing": skipped_existing,
                "dupes_removed": batch_dupes,
                "total_collected": total_collected,
                "years_completed": years_completed,
                "years_total": num_years,
                "elapsed_sec": round(time.time() - crawl_start_time),
                "year_breakdown": year_breakdown,
            })
            logger.info(
                f"📰 {year}년: +{saved}건 저장 (신규 NYT {nyt_new}, Guardian {guardian_new}, "
                f"기존URL 스킵 {skipped_existing}, 배치중복 {batch_dupes}) "
                f"(누적 {total_collected}/{TARGET_TOTAL})"
            )
        else:
            years_completed += 1
            year_info = {
                "year": year,
                "nyt_fetched": 0, "guardian_fetched": 0,
                "nyt_new": 0, "guardian_new": 0,
                "saved": 0, "skipped_existing": 0, "dupes_in_batch": 0,
                "error": error_str,
            }
            year_breakdown.append(year_info)
            emit_json({
                "type": "year_empty", "year": year,
                "years_completed": years_completed, "years_total": num_years,
                "year_breakdown": year_breakdown,
            })
            logger.warning(f"⚠️  {year}년: 수집된 기사 없음")

        state["last_completed_year"] = year
        state["total_collected"] = total_collected
        save_state(state)

    total_elapsed = round(time.time() - crawl_start_time)
    emit_json({
        "type": "complete",
        "total_collected": total_collected,
        "total_nyt": total_nyt,
        "total_guardian": total_guardian,
        "total_dupes": total_dupes,
        "total_skipped_existing": total_skipped_existing,
        "years_completed": years_completed,
        "elapsed_sec": total_elapsed,
        "year_breakdown": year_breakdown,
    })
    logger.info(f"✅ 크롤링 완료! 총 {total_collected}건 수집됨. (기존URL 스킵: {total_skipped_existing}건, 소요: {total_elapsed}초)")
    await db.close()


async def _load_existing_article_ids(db: Database) -> set:
    """DB에서 기존 기사 ID(URL 해시) 전체를 로드하여 set으로 반환"""
    from app.models.news_article import NewsArticle as NA
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(NA.id))
        return {row[0] for row in result.all()}


def main():
    global TARGET_TOTAL

    parser = argparse.ArgumentParser(description="NYT & Guardian 과거 기사 크롤러 (2000~현재)")
    parser.add_argument("--start", type=int, default=None, help="시작 연도")
    parser.add_argument("--end", type=int, default=None, help="종료 연도 (--start와 같으면 단독 연도 수집)")
    parser.add_argument("--stop", action="store_true", help="크롤링 상태 초기화")
    parser.add_argument("--target", type=int, default=2000, help="목표 수집 건수 (기본: 2000)")
    args = parser.parse_args()

    if args.stop:
        clear_state()
        return

    TARGET_TOTAL = args.target

    asyncio.run(crawl_all(start_year_override=args.start, end_year_override=args.end))


if __name__ == "__main__":
    main()
