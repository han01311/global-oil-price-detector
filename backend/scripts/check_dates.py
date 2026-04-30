import asyncio
from app.core.database import Database
from app.models.base import get_session_factory
from sqlalchemy import text

async def main():
    db = Database()
    await db.connect()
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(text("SELECT published_at FROM news_articles WHERE is_classified = 1 ORDER BY published_at DESC LIMIT 15"))
        rows = result.mappings().all()
        for r in rows:
            print(r['published_at'])

asyncio.run(main())
