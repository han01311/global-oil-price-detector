import asyncio
from datetime import datetime, timezone, timedelta
from app.services.briefing_generator import BriefingGenerator
from app.api.forecast import _run_forecast_pipeline
from app.core.database import Database
from app.services.scheduler import _fetch_crude_price_data

async def main():
    db = Database()
    await db.connect()
    
    # 최근 2일간의 뉴스 가져오기
    two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    rows = await db.fetch_all("SELECT * FROM news_articles WHERE classified_at IS NOT NULL AND published_at > $1 ORDER BY published_at DESC LIMIT 10", two_days_ago)
    
    classified_articles = []
    for r in rows:
        article = dict(r)
        if article.get('impact_by_crude'):
            import json
            article['impact_by_crude'] = json.loads(article['impact_by_crude'])
        classified_articles.append(article)
        
    print(f"Found {len(classified_articles)} recently classified articles.")
    
    price_data = await _fetch_crude_price_data(db)
    forecast_result, _, _ = await _run_forecast_pipeline()
    
    generator = BriefingGenerator()
    briefing = await generator.generate_briefing(
        forecast=forecast_result,
        classified_articles=classified_articles,
        price_data=price_data,
        force=True,
    )
    print("Briefing generated successfully!")

asyncio.run(main())
