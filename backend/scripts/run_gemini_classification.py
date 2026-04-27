import asyncio
import sys
import os
import re
import json
import time
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai
from sqlalchemy import select, update
from app.core.database import get_session_factory
from app.models.news_article import NewsArticle as NewsArticleModel
from app.schemas.news import NewsArticle, ClassifiedArticle, CrudeImpact
from app.services.market_memory import MarketMemory
from app.services.news_classifier import NewsClassifier

async def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not found in environment. Exiting.")
        return

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"response_mime_type": "application/json"})
    text_model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"response_mime_type": "text/plain"})
    
    classifier = NewsClassifier()
    memory = MarketMemory()
    SessionLocal = get_session_factory()
    
    # 1. Fetch all IDs to process (avoiding long-running session locks)
    async with SessionLocal() as db:
        result = await db.execute(select(NewsArticleModel).where(NewsArticleModel.is_classified == 0).order_by(NewsArticleModel.published_at.desc()))
        articles = result.scalars().all()
        # Convert to dict to avoid detached instance errors
        article_dicts = []
        for a in articles:
            article_dicts.append({
                "id": a.id,
                "title": a.title,
                "description": a.description,
                "source_name": a.source_name,
                "url": a.url,
                "published_at": a.published_at,
                "collected_at": a.collected_at,
                "content_snippet": a.content_snippet,
                "data_source": a.data_source
            })
            
    print(f"Found {len(article_dicts)} unclassified articles in DB.")
    
    for i, row in enumerate(article_dicts):
        start_time = time.time()
        print(f"[{i+1}/{len(article_dicts)}] Classifying: {row['title'][:50]}")
        
        # Validation logic
        bad_titles = ["untitled", "no title", ""]
        current_title_clean = row['title'].strip().lower() if row.get('title') else ""
        if not current_title_clean or current_title_clean in bad_titles or len(current_title_clean) < 5:
            fetched_title = await classifier._fetch_title_from_url(row.get('url', ''))
            if fetched_title:
                row['title'] = fetched_title
            else:
                fallback_text = row.get('content_snippet') or row.get('description') or "알 수 없는 기사"
                row['title'] = fallback_text.split('.')[0][:100] + "..."

        schema_article = NewsArticle(
            id=row['id'],
            title=row['title'],
            description=row.get('description', ''),
            source=row.get('source_name', 'Unknown'),
            source_name=row.get('source_name', 'Unknown'),
            url=row.get('url', ''),
            published_at=row.get('published_at', ''),
            collected_at=row.get('collected_at', ''),
            content_snippet=row.get('content_snippet', ' '),
            data_source=row.get('data_source', 'Unknown')
        )
        
        content_to_analyze = f"Title: {schema_article.title}\nDescription: {schema_article.description or ''}\nContent Snippet: {schema_article.content_snippet or ''}"
        prompt = classifier._build_classification_prompt(content_to_analyze)
        
        try:
            response = model.generate_content(prompt)
            response_json = json.loads(response.text)
            
            def is_korean(text):
                if not text: return False
                return len(re.findall(r'[가-힣]', text)) > 3

            original_is_kor = is_korean(schema_article.title)
            if not original_is_kor:
                tt = response_json.get("translated_title", "")
                if not tt or not is_korean(tt) or (len(re.findall(r'[a-zA-Z]', tt)) > len(re.findall(r'[가-힣]', tt))):
                    retry_prompt = f"Translate the following news title into natural Korean. Output ONLY the translated Korean string in plain text. Title: {schema_article.title}"
                    retry_res = text_model.generate_content(retry_prompt)
                    new_title = retry_res.text.strip().strip('"').strip()
                    if is_korean(new_title):
                        response_json["translated_title"] = new_title
                        
            raw_impact = response_json.pop("impact_by_crude", {})
            impact_by_crude = {}
            for crude_type in classifier.CRUDE_TYPES:
                if crude_type in raw_impact:
                    try:
                        impact_by_crude[crude_type] = CrudeImpact(**raw_impact[crude_type])
                    except Exception:
                        impact_by_crude[crude_type] = CrudeImpact()
                else:
                    overall_score = response_json.get("impact_score", 0)
                    direction = "bullish" if overall_score > 0 else ("bearish" if overall_score < 0 else "neutral")
                    impact_by_crude[crude_type] = CrudeImpact(
                        direction=direction, score=overall_score,
                        rationale=response_json.get("impact_summary", "")
                    )
                    
            result_data = {
                "article": schema_article,
                "classified_at": datetime.now(timezone.utc).isoformat(),
                "impact_by_crude": impact_by_crude,
                **response_json
            }
            
            classified_article = ClassifiedArticle(**result_data)
            
            if classified_article.is_relevant:
                price_changes = {}
                for crude in ["dubai", "brent", "wti"]:
                    for period in ["1d", "7d", "30d"]:
                        price_changes[f"{crude}_change_{period}"] = 0.0
                await memory.store_event(classified_article.model_dump(), price_changes)
                
            # Update DB (Open short-lived session)
            async with SessionLocal() as db_update:
                await db_update.execute(update(NewsArticleModel).where(NewsArticleModel.id == row['id']).values(is_classified=1))
                await db_update.commit()
                
            print(f"  -> Success: {response_json.get('translated_title') or response_json.get('impact_summary')[:20]}")
            
        except Exception as e:
            print(f"  -> Failed: {e}")
            
        # Free Tier Rate Limiting (15 RPM -> Max 1 request per 4.1s)
        elapsed = time.time() - start_time
        if elapsed < 4.1:
            await asyncio.sleep(4.1 - elapsed)
            
    print("All articles processed.")

if __name__ == "__main__":
    asyncio.run(main())
