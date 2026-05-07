from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
import os
import json
import logging
from datetime import datetime, timedelta, timezone
from pydantic import ValidationError

from app.schemas.forecast import Briefing
from app.services.briefing_generator import BriefingGenerator

router = APIRouter(prefix="/api/briefing", tags=["briefing"])
logger = logging.getLogger(__name__)

@router.get("/today", response_model=Briefing)
async def get_today_briefing() -> Briefing:
    """오늘의 유가 브리핑 조회 — 캐시 읽기 전용 (on-demand 생성 안 함)"""
    generator = BriefingGenerator()
    
    cached_briefing = generator._load_from_cache()
    if cached_briefing:
        return cached_briefing
    
    # 캐시에 없으면 브리핑이 아직 생성되지 않은 것
    raise HTTPException(
        status_code=404,
        detail="오늘의 브리핑이 아직 생성되지 않았습니다. 뉴스 수집 및 분류 완료 후 자동 생성됩니다."
    )


@router.post("/generate", response_model=Briefing)
async def generate_briefing() -> Briefing:
    """브리핑 강제 재생성 (관리자용 — 수동 트리거)"""
    from app.api.forecast import _run_forecast_pipeline
    from app.services.market_memory import MarketMemory
    from app.core.database import Database
    from app.services.scheduler import _fetch_crude_price_data

    generator = BriefingGenerator()

    try:
        # 1. 가격 데이터 조회
        db = Database()
        price_data = await _fetch_crude_price_data(db)

        # 2. 예측 파이프라인 실행
        forecast_result, relevant_articles, _, _ = await _run_forecast_pipeline()
        
        # 3. 인메모리 기사 없으면 ChromaDB에서 로드
        if not relevant_articles:
            logger.info("No in-memory news cache. Loading classified articles from ChromaDB.")
            memory = MarketMemory()
            if memory.is_available():
                cached_classified = memory.get_recent_classified_articles(limit=20)
                relevant_articles = [
                    a.model_dump() for a in cached_classified if a.is_relevant
                ]
                logger.info(f"Loaded {len(relevant_articles)} articles from ChromaDB for briefing.")

        # 4. 브리핑 강제 재생성
        briefing = await generator.generate_briefing(
            forecast=forecast_result,
            classified_articles=relevant_articles,
            price_data=price_data,
            force=True,
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
