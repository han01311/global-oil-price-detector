import asyncio
from app.core.database import Database
from app.services.news_classifier import NewsClassifier

async def main():
    db = Database()
    await db.connect()
    raw = await db.get_news_articles(limit=50)
    
    # Filter unclassified
    unclassified = [r for r in raw if r['is_classified'] == 0]
    print(f"Found {len(unclassified)} unclassified articles in the latest 50.")
    
    if unclassified:
        classifier = NewsClassifier()
        await classifier.classify_batch(unclassified)
        print("Classification complete.")
    else:
        print("No unclassified articles.")

if __name__ == "__main__":
    asyncio.run(main())
