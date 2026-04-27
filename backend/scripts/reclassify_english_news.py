import asyncio
import sys
import os
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.news import NewsArticle
from app.services.news_classifier import NewsClassifier

def is_english(text):
    if not text: return False
    eng_chars = len(re.findall(r'[a-zA-Z]', text))
    kor_chars = len(re.findall(r'[가-힣]', text))
    return eng_chars > kor_chars

async def main():
    classifier = NewsClassifier()
    db = SessionLocal()
    try:
        articles = db.query(NewsArticle).all()
        print(f"Total articles in DB: {len(articles)}")
        
        eng_articles = [a for a in articles if is_english(a.content) or is_english(a.title)]
        print(f"Found {len(eng_articles)} English articles to re-classify.")
        
        for i, article in enumerate(eng_articles):
            print(f"[{i+1}/{len(eng_articles)}] Re-classifying: {article.title[:50]}...")
            
            # Use content or description if content is empty
            text_to_analyze = article.content if article.content and len(article.content) > 50 else article.description
            if not text_to_analyze:
                continue
                
            result = await classifier.classify_article(text_to_analyze)
            
            if result:
                article.is_relevant = result.is_relevant
                article.category = result.category
                article.sub_categories = result.sub_categories
                article.impact_score = result.impact_score
                article.impact_summary = result.impact_summary
                article.impact_by_crude = result.impact_by_crude
                article.confidence = result.confidence
                article.translated_title = result.translated_title
                
                db.commit()
                print(f"  -> Updated! Summary: {result.impact_summary[:50]}...")
                
            # Sleep slightly to avoid rate limits
            await asyncio.sleep(2)
            
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
