import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.core.database import Database
from app.api.news import get_news_by_date

async def main():
    try:
        articles = await get_news_by_date("2023", 5)
        print(f"Success! returned {len(articles)} articles.")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
