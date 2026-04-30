import asyncio
from app.services.briefing_generator import BriefingGenerator
from app.api.forecast import _run_forecast_pipeline
from app.core.database import Database
from app.models.base import get_session_factory
from app.services.scheduler import _fetch_crude_price_data
import json
from sqlalchemy import text

async def main():
    db = Database()
    await db.connect()
    
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(text("SELECT * FROM news_articles WHERE is_classified = 1 ORDER BY published_at DESC LIMIT 10"))
        rows = result.mappings().all()
    
    classified_articles = []
    for r in rows:
        res = r.get('classification_result')
        if isinstance(res, str):
            res = json.loads(res)
            
        if not res:
            continue
            
        article_dict = dict(r)
        for k, v in res.items():
            article_dict[k] = v
            
        if 'is_relevant' not in article_dict:
            article_dict['is_relevant'] = True
            
        classified_articles.append(article_dict)
        
    print(f"Found {len(classified_articles)} recently classified articles.")
    
    price_data = await _fetch_crude_price_data(db)
    forecast_result, _, _, _ = await _run_forecast_pipeline()
    
    generator = BriefingGenerator()
    briefing = await generator.generate_briefing(
        forecast=forecast_result,
        classified_articles=classified_articles,
        price_data=price_data,
        force=True,
    )
    print("Briefing generated successfully!")

asyncio.run(main())
