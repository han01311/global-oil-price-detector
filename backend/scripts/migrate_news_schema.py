import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from app.core.database import get_session_factory

async def main():
    SessionLocal = get_session_factory()
    try:
        async with SessionLocal() as session:
            await session.execute(text("ALTER TABLE news_articles ADD COLUMN classification_result JSONB;"))
            await session.commit()
            print("Successfully added classification_result column to news_articles.")
    except Exception as e:
        print(f"Error (might already exist): {e}")

if __name__ == "__main__":
    asyncio.run(main())
