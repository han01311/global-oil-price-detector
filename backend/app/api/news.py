from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timezone
from app.services.data_collector import DataCollector
from app.schemas.news import NewsCollection, NewsArticle

router = APIRouter(prefix="/api/news", tags=["news"])

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
