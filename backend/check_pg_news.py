import sys
import os
from pathlib import Path

# Add backend dir to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.database import Database

async def main():
    db = Database()
    count = await db.get_news_articles_count()
    print(f"Total News Articles in PostgreSQL: {count}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
