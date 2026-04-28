import asyncio
import logging
from sqlalchemy import select
from app.models.base import get_session_factory
from app.models.news_article import NewsArticle
from app.services.news_classifier import NewsClassifier

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Backfill")

async def main():
    session_factory = get_session_factory()
    
    # 1. Fetch articles needing re-classification
    async with session_factory() as session:
        result = await session.execute(
            select(NewsArticle).where(NewsArticle.is_classified == 1)
        )
        articles = result.scalars().all()
        
    to_reclassify = []
    for a in articles:
        c_res = a.classification_result
        if not c_res or not c_res.get('sub_categories') or len(c_res.get('sub_categories')) == 0:
            to_reclassify.append(a)
            
    logger.info(f"Found {len(to_reclassify)} articles missing sub_categories.")
    
    if not to_reclassify:
        return
        
    # Convert to list of dicts for classifier
    articles_dict = []
    for a in to_reclassify:
        articles_dict.append({
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "source": a.source_name,
            "url": a.url,
            "published_at": a.published_at,
            "content_snippet": a.content_snippet,
            "data_source": a.data_source
        })
        
    # 2. Run classifier (this saves to Postgres and MarketMemory automatically!)
    classifier = NewsClassifier()
    logger.info(f"Starting batch classification for {len(articles_dict)} articles...")
    await classifier.classify_batch(articles_dict)
    logger.info("Backfill completed!")

if __name__ == "__main__":
    asyncio.run(main())
