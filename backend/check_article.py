import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import json

DATABASE_URL = "postgresql+asyncpg://petroax:petroax_dev_2026@localhost:5432/petroax"

async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT is_classified, classification_result, classification_error
                FROM news_articles 
                WHERE id = '9ecb861338ac7684aee54f6c1c4484a00f445f235af9c8c1b715fd8edfa90ac1'
            """)
        )
        row = result.fetchone()
        if row:
            print(f"Is Classified: {row[0]}")
            print(f"Classification Result: {json.dumps(row[1], indent=2, ensure_ascii=False) if row[1] else 'None'}")
            print(f"Classification Error: {row[2]}")
        else:
            print("Article not found.")

if __name__ == "__main__":
    asyncio.run(main())
