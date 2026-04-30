from fastapi import APIRouter, Query, HTTPException, Body
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List

from app.services.data_collector import DataCollector
from app.services.news_classifier import NewsClassifier
from app.services.market_memory import MarketMemory
from app.schemas.news import (
    NewsCollection, NewsArticle, ClassifiedArticle,
    SimilarEvent, FactorScore, FactorSummary
)

router = APIRouter(prefix="/api/news", tags=["news"])

_news_cache = {"data": None, "expires_at": 0}
_news_cache_lock = asyncio.Lock()


# ──────────────────────────────────────────────
# 공통 유틸리티
# ──────────────────────────────────────────────

def _convert_raw_to_classified(raw_articles: list[dict]) -> List[ClassifiedArticle]:
    classified_articles = []
    from datetime import datetime, timezone
    for raw in raw_articles:
        base_article = NewsArticle(
            id=raw["id"],
            title=raw["title"],
            description=raw.get("description", ""),
            source=raw.get("source_name", "Unknown"),
            source_name=raw.get("source_name", "Unknown"),
            url=raw["url"],
            published_at=raw.get("published_at", ""),
            collected_at=raw.get("collected_at", ""),
            content_snippet=raw.get("content_snippet", " "),
            data_source=raw.get("data_source", "Unknown")
        )
        
        c_result = raw.get("classification_result")
        if raw.get("is_classified") == 1 and c_result:
            classified_articles.append(ClassifiedArticle(
                article=base_article,
                translated_title=c_result.get("translated_title"),
                impact_summary=c_result.get("impact_summary") or "",
                impact_score=c_result.get("impact_score", 0),
                confidence=c_result.get("confidence", 1.0),
                is_relevant=c_result.get("is_relevant", True),
                category=c_result.get("category", "unknown"),
                sub_categories=c_result.get("sub_categories", []),
                impact_by_crude=c_result.get("impact_by_crude", {}),
                classified_at=c_result.get("classified_at") or datetime.now(timezone.utc).isoformat()
            ))
        else:
            classified_articles.append(ClassifiedArticle(
                article=base_article,
                is_relevant=True,
                category="unknown",
                sub_categories=[],
                impact_score=0,
                impact_summary="",
                confidence=1.0,
                classified_at=datetime.now(timezone.utc).isoformat(),
                impact_by_crude={}
            ))
    return classified_articles


# ──────────────────────────────────────────────
# DB 기사 조회 (차트 마커 + 날짜 필터용)
# ──────────────────────────────────────────────

@router.get("/date-counts")
async def get_news_date_counts(
    start_date: str = Query(..., description="시작일 YYYY-MM-DD"),
    end_date: str = Query(..., description="종료일 YYYY-MM-DD"),
):
    """날짜별 기사 건수 (Price Chart 마커용)"""
    from app.core.database import Database
    db = Database()
    await db.connect()
    counts = await db.get_news_date_counts(start_date, end_date)
    # 날짜별로 합산: {date: total_count}
    merged: dict = {}
    for row in counts:
        d = row["date"]
        if d not in merged:
            merged[d] = {"date": d, "count": 0, "sources": []}
        merged[d]["count"] += row["count"]
        merged[d]["sources"].append({"source": row["data_source"], "count": row["count"]})
    return list(merged.values())


@router.get("/by-date", response_model=List[ClassifiedArticle])
async def get_news_by_date(
    date: str = Query(..., description="날짜 YYYY-MM-DD"),
    limit: int = Query(default=200, le=500),
) -> List[ClassifiedArticle]:
    """특정 날짜의 기사 목록 (News Explorer 날짜 필터용)"""
    from app.core.database import Database
    db = Database()
    await db.connect()
    raw_articles = await db.get_news_by_date(date, limit)
    return _convert_raw_to_classified(raw_articles)


@router.get("/by-range", response_model=List[ClassifiedArticle])
async def get_news_by_range(
    start_date: str = Query(..., description="조회 시작일 (YYYY-MM-DD)"),
    end_date: str = Query(..., description="조회 종료일 (YYYY-MM-DD)"),
    limit: int = Query(default=500, le=1000),
) -> List[ClassifiedArticle]:
    """특정 기간의 기사 목록 (News Explorer 범위 필터용)"""
    from app.core.database import Database
    db = Database()
    await db.connect()
    raw_articles = await db.get_news_by_range(start_date, end_date, limit)
    return _convert_raw_to_classified(raw_articles)


async def _classify_articles_payload(
    articles_to_classify: list[dict],
    *,
    cache_fetch_latest: bool = False,
) -> List[ClassifiedArticle]:
    if not articles_to_classify:
        return []

    classifier = NewsClassifier()
    if not classifier.ollama_url:
        raise HTTPException(status_code=503, detail="NewsClassifier is not available. Check LOCAL_LLM_URL.")

    try:
        classified_results = await classifier.classify_batch(articles_to_classify)

        # Store relevant articles to MarketMemory for FactorGauge to pick up
        memory = MarketMemory()
        if memory.is_available() and classified_results:
            for res in classified_results:
                if res.is_relevant:
                    from app.core.database import Database
                    db_instance = Database()
                    price_changes = await db_instance.get_historical_price_changes(res.article.published_at)
                    await memory.store_event(res.model_dump(), price_changes)

        if cache_fetch_latest:
            _news_cache["data"] = classified_results
            _news_cache["expires_at"] = datetime.now().timestamp() + 3600

        return classified_results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during classification: {e}")

@router.get("/latest", response_model=NewsCollection)
async def get_latest_news(
    limit: int = Query(default=20, le=50),
) -> NewsCollection:
    """최신 유가 관련 뉴스 조회"""
    try:
        collector = DataCollector()
        articles_data = await collector.collect_news()
        
        # Pydantic 모델로 변환
        articles = [NewsArticle(**article) for article in articles_data]

        # 최신순으로 정렬
        articles.sort(key=lambda x: x.published_at, reverse=True)
        
        limited_articles = articles[:limit]

        return NewsCollection(
            articles=limited_articles,
            query_keywords=collector.news.KEYWORDS,
            collected_at=datetime.now(timezone.utc).isoformat(),
            total_count=len(limited_articles)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/classify", response_model=List[ClassifiedArticle])
async def classify_news(
    articles: List[NewsArticle] = Body(default=None),
    fetch_latest: bool = Query(default=False),
    force_refresh: bool = Query(default=False),
) -> List[ClassifiedArticle]:
    """
    뉴스 기사를 분류하고 영향도를 평가한다
    - articles 제공 시: 해당 기사를 분류
    - fetch_latest=True 시: 최신 뉴스를 수집하여 분류
    """
    if not articles and not fetch_latest:
        raise HTTPException(
            status_code=400,
            detail="Either 'articles' must be provided in the body or 'fetch_latest' must be set to true."
        )

    current_time = datetime.now().timestamp()
    cacheable_latest = fetch_latest and not articles
    if cacheable_latest and not force_refresh and _news_cache["data"] is not None and current_time < _news_cache["expires_at"]:
        return _news_cache["data"]

    articles_to_classify = []
    if cacheable_latest and not force_refresh:
        from app.core.database import Database
        db_instance = Database()
        await db_instance.connect()
        raw_articles = await db_instance.get_news_articles(limit=100)
        cached_articles = _convert_raw_to_classified(raw_articles)
        
        # Only return cached articles if we actually got some valid classified ones
        # and they are reasonably fresh (handled loosely by sqlite order)
        if cached_articles and len([a for a in cached_articles if a.is_relevant]) > 0:
            _news_cache["data"] = cached_articles
            _news_cache["expires_at"] = datetime.now().timestamp() + 3600
            return cached_articles

    if cacheable_latest:
        async with _news_cache_lock:
            current_time = datetime.now().timestamp()
            if not force_refresh and _news_cache["data"] is not None and current_time < _news_cache["expires_at"]:
                return _news_cache["data"]
            try:
                collector = DataCollector()
                latest_articles_data = await collector.collect_news()
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to fetch latest news: {e}")
            return await _classify_articles_payload(latest_articles_data, cache_fetch_latest=True)

    if fetch_latest:
        try:
            collector = DataCollector()
            latest_articles_data = await collector.collect_news()
            articles_to_classify.extend(latest_articles_data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch latest news: {e}")
    
    if articles:
        # Convert Pydantic models to dicts for the classifier
        articles_to_classify.extend([article.model_dump() for article in articles])

    return await _classify_articles_payload(articles_to_classify)


@router.get("/similar", response_model=List[SimilarEvent])
async def search_similar_events(
    query: str = Query(..., min_length=3, description="검색 쿼리 (뉴스 제목 또는 키워드)"),
    category: str = Query(default=None, description="필터링할 카테고리"),
    crude_type: str = Query(default=None, description="특정 유종 필터 (dubai, brent, wti)"),
    limit: int = Query(default=5, ge=1, le=20),
) -> List[SimilarEvent]:
    """유사 과거 사례 검색"""
    memory = MarketMemory()
    if not memory.is_available():
        raise HTTPException(status_code=503, detail="MarketMemory is not available.")

    try:
        search_results = await memory.search_similar(query=query, category=category, crude_type=crude_type, n_results=limit)
        
        response_events = []
        for res in search_results:
            metadata = res.get('metadata', {})
            
            # Helper to convert -9999.0 back to None
            def get_change(key):
                val = metadata.get(key)
                return None if val == -9999.0 else val

            event = SimilarEvent(
                title=res.get('document', '').split('\n')[0].replace('Title: ', ''),
                translated_title=metadata.get('translated_title'),
                summary=res.get('document', '').split('\n')[1].replace('Summary: ', '') if '\n' in res.get('document', '') else '',
                category=metadata.get('category', 'unknown'),
                impact_score=metadata.get('impact_score', 0),
                date=metadata.get('date', ''),
                url=metadata.get('url', ''),
                wti_change_1d=get_change('wti_change_1d'),
                wti_change_7d=get_change('wti_change_7d'),
                wti_change_30d=get_change('wti_change_30d'),
                dubai_change_1d=get_change('dubai_change_1d'),
                dubai_change_7d=get_change('dubai_change_7d'),
                dubai_change_30d=get_change('dubai_change_30d'),
                brent_change_1d=get_change('brent_change_1d'),
                brent_change_7d=get_change('brent_change_7d'),
                brent_change_30d=get_change('brent_change_30d'),
                similarity=1.0 - res.get('distance', 1.0)
            )
            response_events.append(event)
        
        return response_events
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during search: {e}")


@router.get("/factors/summary", response_model=FactorSummary)
async def get_factor_summary() -> FactorSummary:
    """최근 24시간 동안의 6대 요인별 종합 스코어 반환"""
    memory = MarketMemory()
    if not memory.is_available():
        raise HTTPException(status_code=503, detail="MarketMemory is not available.")

    try:
        # Get all events from the collection
        all_events = memory._collection.get(include=["metadatas"])
        
        if not all_events or not all_events['metadatas']:
            return FactorSummary(factors=[], overall_sentiment=0.0, updated_at=datetime.now(timezone.utc).isoformat())

        # Filter for the last 7 days
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        
        recent_events = []
        for metadata in all_events['metadatas']:
            event_date_str = metadata.get('date')
            if event_date_str:
                try:
                    event_date = datetime.strptime(event_date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                    if event_date >= seven_days_ago:
                        recent_events.append(metadata)
                except ValueError:
                    continue # Skip if date format is wrong

        # Calculate stats
        stats = {}
        total_weighted_impact = 0
        total_articles = 0

        for event in recent_events:
            category = event.get('category')
            impact_score = event.get('impact_score')
            
            if category and isinstance(impact_score, (int, float)):
                if category not in stats:
                    stats[category] = {'total_impact': 0, 'count': 0}
                stats[category]['total_impact'] += impact_score
                stats[category]['count'] += 1
                total_weighted_impact += impact_score
                total_articles += 1

        factor_scores = []
        for category, data in stats.items():
            avg_score = data['total_impact'] / data['count'] if data['count'] > 0 else 0
            
            trend = "neutral"
            if avg_score > 0.5: trend = "bullish"
            elif avg_score < -0.5: trend = "bearish"

            factor_scores.append(FactorScore(
                category=category,
                avg_score=round(avg_score, 2),
                article_count=data['count'],
                trend=trend
            ))
        
        overall_sentiment = total_weighted_impact / total_articles if total_articles > 0 else 0

        return FactorSummary(
            factors=sorted(factor_scores, key=lambda x: x.category),
            overall_sentiment=round(overall_sentiment, 2),
            updated_at=now.isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get factor summary: {e}")
