import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.database import Database

async def main():
    db = Database()
    await db.connect()
    res = await db.get_news_articles(limit=5)
    for r in res:
        print(r['published_at'])
        
if __name__ == '__main__':
    asyncio.run(main())
