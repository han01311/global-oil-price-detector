import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import update
from app.core.database import get_session_factory
from app.models.news_article import NewsArticle as NewsArticleModel
from app.services.market_memory import MarketMemory
from app.schemas.news import CrudeImpact

async def main():
    memory = MarketMemory()
    SessionLocal = get_session_factory()
    
    if not memory.is_available():
        print("MarketMemory not available.")
        return
        
    try:
        # Get all articles from ChromaDB
        result = memory._collection.get(include=["metadatas", "documents"])
        ids = result.get("ids", [])
        metadatas = result.get("metadatas", [])
        
        print(f"Found {len(ids)} items in ChromaDB.")
        
        updated_count = 0
        
        async with SessionLocal() as db:
            for article_id, metadata in zip(ids, metadatas):
                impact_by_crude = {}
                for crude in ["dubai", "brent", "wti"]:
                    impact_by_crude[crude] = {
                        "direction": metadata.get(f"{crude}_direction", "neutral"),
                        "score": int(metadata.get(f"{crude}_score", metadata.get("impact_score", 0)) or 0),
                        "rationale": ""
                    }
                
                classification_json = {
                    "translated_title": metadata.get("translated_title"),
                    "impact_summary": "",
                    "impact_score": metadata.get("impact_score", 0),
                    "confidence": 1.0,
                    "is_relevant": True,
                    "category": metadata.get("category", "unknown"),
                    "sub_categories": [],
                    "impact_by_crude": impact_by_crude
                }
                
                stmt = update(NewsArticleModel).where(NewsArticleModel.id == article_id).values(
                    is_classified=1,
                    classification_result=classification_json
                )
                res = await db.execute(stmt)
                if res.rowcount > 0:
                    updated_count += 1
            
            await db.commit()
            print(f"Successfully updated {updated_count} articles in PostgreSQL.")
            
    except Exception as e:
        print(f"Error during backfill: {e}")

if __name__ == "__main__":
    asyncio.run(main())
