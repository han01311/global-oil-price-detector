import asyncio
from sqlalchemy import select
from app.models.base import get_session_factory
from app.models.news_article import NewsArticle

async def main():
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(NewsArticle).where(NewsArticle.is_classified == 1)
        )
        articles = result.scalars().all()
        missing_count = sum(1 for a in articles if not a.classification_result or not a.classification_result.get('sub_categories'))
        print(f"Total classified: {len(articles)}, Missing sub_categories: {missing_count}")

if __name__ == "__main__":
    asyncio.run(main())
