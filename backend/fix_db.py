import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://petroax:petroax_dev_2026@localhost:5432/petroax"

async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        url = "https://www.nytimes.com/1985/06/18/business/mexico-cuts-a-key-oil-price.html"
        await session.execute(
            text("""
                UPDATE news_articles
                SET title = 'MEXICO CUTS A KEY OIL PRICE',
                    source_name = 'The New York Times',
                    data_source = 'nyt',
                    published_at = '1985-06-18T00:00:00Z',
                    is_classified = 0
                WHERE url = :url
            """),
            {"url": url}
        )
        await session.commit()
        print("Updated successfully")

if __name__ == "__main__":
    asyncio.run(main())
