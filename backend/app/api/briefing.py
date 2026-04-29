from fastapi import APIRouter, Query, HTTPException
from typing import List
import os
import json
import logging
from datetime import datetime, timedelta, timezone
from pydantic import ValidationError

from app.schemas.forecast import Briefing
from app.services.briefing_generator import BriefingGenerator
from app.services.market_memory import MarketMemory
from app.api.forecast import _run_forecast_pipeline

router = APIRouter(prefix="/api/briefing", tags=["briefing"])
logger = logging.getLogger(__name__)

@router.get("/today", response_model=Briefing)
async def get_today_briefing() -> Briefing:
    """오늘의 유가 브리핑 조회 (캐시 있으면 캐시 반환)"""
    generator = BriefingGenerator()
    
    cached_briefing = generator._load_from_cache()
    if cached_briefing:
        return cached_briefing
    
    try:
        forecast_result, relevant_articles, similar_events = await _run_forecast_pipeline()
        
        # If pipeline returned no articles, fall back to ChromaDB cached articles
        if not relevant_articles:
            logger.info("No in-memory news cache. Loading classified articles from ChromaDB.")
            memory = MarketMemory()
            if memory.is_available():
                cached_classified = memory.get_recent_classified_articles(limit=20)
                relevant_articles = [
                    a.model_dump() for a in cached_classified if a.is_relevant
                ]
                # Also search for similar events if we now have articles
                if relevant_articles and not similar_events:
                    most_impactful = max(relevant_articles, key=lambda x: abs(x.get('impact_score', 0)))
                    query_text = most_impactful.get('article', {}).get('title', '')
                    if query_text:
                        search_results = await memory.search_similar(query=query_text, n_results=5)
                        for res in search_results:
                            metadata = res.get('metadata', {})
                            def get_change(key):
                                val = metadata.get(key)
                                if val is None or val == -1.0 or val == -9999.0 or val <= -9990:
                                    return None
                                return val
                            similar_events.append({
                                "title": res.get('document', '').split('\n')[0].replace('Title: ', ''),
                                "similarity": 1.0 - res.get('distance', 1.0),
                                "wti_change_7d": get_change('wti_change_7d'),
                                "dubai_change_7d": get_change('dubai_change_7d'),
                                "brent_change_7d": get_change('brent_change_7d'),
                            })
                logger.info(f"Loaded {len(relevant_articles)} articles from ChromaDB for briefing.")
        
        briefing = await generator.generate_briefing(
            forecast=forecast_result,
            classified_articles=relevant_articles,
            similar_events=similar_events
        )
        return briefing
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate briefing: {str(e)}")

@router.post("/generate", response_model=Briefing)
async def generate_briefing() -> Briefing:
    """브리핑 강제 재생성 (캐시 무시)"""
    generator = BriefingGenerator()
    
    cache_path = generator._get_cache_path()
    if os.path.exists(cache_path):
        try:
            os.remove(cache_path)
        except OSError:
            pass

    try:
        forecast_result, relevant_articles, similar_events = await _run_forecast_pipeline()
        
        # If pipeline returned no articles, fall back to ChromaDB cached articles
        if not relevant_articles:
            memory = MarketMemory()
            if memory.is_available():
                cached_classified = memory.get_recent_classified_articles(limit=20)
                relevant_articles = [
                    a.model_dump() for a in cached_classified if a.is_relevant
                ]
                if relevant_articles and not similar_events:
                    most_impactful = max(relevant_articles, key=lambda x: abs(x.get('impact_score', 0)))
                    query_text = most_impactful.get('article', {}).get('title', '')
                    if query_text:
                        search_results = await memory.search_similar(query=query_text, n_results=5)
                        for res in search_results:
                            metadata = res.get('metadata', {})
                            def get_change(key):
                                val = metadata.get(key)
                                if val is None or val == -1.0 or val == -9999.0 or val <= -9990:
                                    return None
                                return val
                            similar_events.append({
                                "title": res.get('document', '').split('\n')[0].replace('Title: ', ''),
                                "similarity": 1.0 - res.get('distance', 1.0),
                                "wti_change_7d": get_change('wti_change_7d'),
                                "dubai_change_7d": get_change('dubai_change_7d'),
                                "brent_change_7d": get_change('brent_change_7d'),
                            })
        
        briefing = await generator.generate_briefing(
            forecast=forecast_result,
            classified_articles=relevant_articles,
            similar_events=similar_events
        )
        return briefing
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate briefing: {str(e)}")


@router.get("/history", response_model=List[Briefing])
async def get_briefing_history(
    days: int = Query(default=7, ge=1, le=30),
) -> List[Briefing]:
    """과거 브리핑 이력 조회"""
    briefings: List[Briefing] = []
    generator = BriefingGenerator()
    cache_dir = generator.CACHE_DIR

    if not os.path.exists(cache_dir):
        return []

    today = datetime.now(timezone.utc).date()
    
    for i in range(days):
        target_date = today - timedelta(days=i)
        file_path = os.path.join(cache_dir, f"{target_date.strftime('%Y-%m-%d')}.json")
        
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    briefings.append(Briefing(**data))
            except (json.JSONDecodeError, ValidationError):
                continue
    
    briefings.sort(key=lambda b: b.date, reverse=True)
    return briefings
