import asyncio
from app.services.data_collector import DataCollector
from app.core.database import Database

async def test_naver_news():
    db = Database()
    await db.connect()
    collector = DataCollector()
    print("Collecting news from Naver API...")
    articles = await collector.collect_news()
    print(f"Collected {len(articles)} articles.")
    for a in articles[:3]:
        print(a['title'], a['url'])
    await db.close()

if __name__ == "__main__":
    asyncio.run(test_naver_news())
