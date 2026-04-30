import asyncio
from app.core.database import get_session_factory
from sqlalchemy import text

async def main():
    sf = get_session_factory()
    async with sf() as session:
        # check duplicate titles in news
        res = await session.execute(text("SELECT title, COUNT(*) as cnt FROM news_articles GROUP BY title HAVING COUNT(*) > 1"))
        dups = [dict(r._mapping) for r in res]
        print(f"News title duplicates: {len(dups)}")
        
asyncio.run(main())
