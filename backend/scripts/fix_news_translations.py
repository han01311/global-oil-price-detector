import asyncio
import sys
import os
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.models.base import get_session_factory
from app.models.news_article import NewsArticle
from app.services.news_classifier import NewsClassifier

def is_korean(text):
    if not text: return False
    return len(re.findall(r'[가-힣]', text)) > 3

async def main():
    classifier = NewsClassifier()
    Session = get_session_factory()
    async with Session() as db:
        result = await db.execute(select(NewsArticle))
        articles = result.scalars().all()
        print(f"Total articles in DB: {len(articles)}")
        
        updates = 0
        reclassifies = 0
        
        for article in articles:
            if is_korean(article.title):
                if article.translated_title:
                    print(f"Fixing KOR article (removing translated_title): {article.title}")
                    article.translated_title = None
                    updates += 1
            else:
                needs_reclassify = False
                if not article.translated_title or article.translated_title == article.title:
                    needs_reclassify = True
                elif not article.impact_summary or not is_korean(article.impact_summary):
                    needs_reclassify = True
                    
                if needs_reclassify:
                    print(f"Re-classifying ENG article: {article.title[:50]}...")
                    text_to_analyze = article.content if article.content and len(article.content) > 50 else article.description
                    if not text_to_analyze:
                        text_to_analyze = article.title
                        
                    res = await classifier.classify_article(text_to_analyze)
                    if res:
                        article.is_relevant = res.is_relevant
                        article.category = res.category
                        article.sub_categories = res.sub_categories
                        article.impact_score = res.impact_score
                        article.impact_summary = res.impact_summary
                        article.impact_by_crude = res.impact_by_crude
                        article.confidence = res.confidence
                        article.translated_title = res.translated_title
                        reclassifies += 1
                        print(f"  -> Successfully translated! New Title: {article.translated_title}")
                    await asyncio.sleep(2)
                    
        await db.commit()
        print(f"Done! Cleaned {updates} Korean articles, re-classified {reclassifies} English articles.")

if __name__ == "__main__":
    asyncio.run(main())
