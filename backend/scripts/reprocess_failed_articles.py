import asyncio
import httpx
from bs4 import BeautifulSoup
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_session_factory
from app.models.news_article import NewsArticle
from sqlalchemy import select, update

async def fetch_article_content(url):
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                paragraphs = [p.text for p in soup.find_all("p") if len(p.text.strip()) > 20]
                text = " ".join(paragraphs)
                if len(text) > 200:
                    return text[:1500]  # First 1500 chars for LLM
    except Exception as e:
        print(f"Fetch failed for {url}: {e}")
    return None

async def main():
    SessionLocal = get_session_factory()
    async with SessionLocal() as session:
        stmt = select(NewsArticle).where(NewsArticle.is_classified == 1)
        result = await session.execute(stmt)
        articles = result.scalars().all()
        
        to_reprocess = []
        for a in articles:
            if not a.classification_result: continue
            cr = a.classification_result
            if isinstance(cr, str):
                try: cr = json.loads(cr)
                except: continue
                
            summary = cr.get("impact_summary", "")
            title = cr.get("translated_title", "")
            original_title = a.title
            
            is_korean = lambda t: any("\uac00" <= c <= "\ud7a3" for c in t) if t else False
            
            if not summary or len(summary) < 10 or (not title and not is_korean(original_title)):
                to_reprocess.append(a)
                
        print(f"Found {len(to_reprocess)} articles missing summary or translation.")
        
        count = 0
        for a in to_reprocess:
            print(f"Processing: {a.title[:50]}...")
            new_content = await fetch_article_content(a.url)
            
            # Update DB to reset classification and add new content if found
            update_data = {"is_classified": 0}
            if new_content:
                print(f"  -> Fetched {len(new_content)} chars.")
                update_data["content_snippet"] = new_content
            else:
                print("  -> Could not fetch new content. Will retry classification with title/desc.")
                
            stmt = update(NewsArticle).where(NewsArticle.id == a.id).values(**update_data)
            await session.execute(stmt)
            count += 1
            
        await session.commit()
        print(f"Successfully reset {count} articles for re-classification.")

if __name__ == "__main__":
    asyncio.run(main())
