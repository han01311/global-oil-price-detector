import sys
import asyncio
from pathlib import Path
import logging

# Add backend dir to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import Database
from app.services.news_classifier import NewsClassifier
from app.services.market_memory import MarketMemory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_backfill():
    db = Database()
    await db.connect()
    
    classifier = NewsClassifier()
    memory = MarketMemory()
    
    if not memory.is_available():
        logger.error("MarketMemory is not available.")
        return
        
    # Get total count for progress reporting
    total_articles = await db.get_news_articles_count()
    logger.info(f"Found {total_articles} articles in PostgreSQL to backfill.")
        
    batch_size = 50
    offset = 0
    total_processed = 0
    
    while True:
        logger.info(f"Fetching articles offset={offset}, limit={batch_size}")
        articles = await db.get_news_articles(limit=batch_size, offset=offset)
        
        if not articles:
            logger.info("No more articles to process. Backfill complete.")
            break
            
        for a in articles:
            if 'source' not in a or not a['source']:
                a['source'] = a.get('data_source') or 'Unknown'
        
        logger.info(f"Classifying {len(articles)} articles... (Batch {offset//batch_size + 1})")
        
        # Classify batch. 
        # Note: classify_batch automatically skips articles already present in ChromaDB.
        classified_results = await classifier.classify_batch(articles)
        
        # Store results in ChromaDB
        if classified_results:
            newly_stored = 0
            for res in classified_results:
                if res.is_relevant:
                    # In backfill, we don't calculate historical price changes right away to save time,
                    # but we supply default 0.0s for the schema requirement.
                    price_changes = {}
                    for crude in ["dubai", "brent", "wti"]:
                        for period in ["1d", "7d", "30d"]:
                            price_changes[f"{crude}_change_{period}"] = 0.0
                    await memory.store_event(res.model_dump(), price_changes)
                    newly_stored += 1
            logger.info(f"Stored {newly_stored} relevant articles from this batch into MarketMemory.")
        
        total_processed += len(articles)
        logger.info(f"Progress: {total_processed}/{total_articles} ({total_processed/total_articles*100:.1f}%)")
        offset += batch_size
        
        # Small delay to let the system breathe
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(run_backfill())
