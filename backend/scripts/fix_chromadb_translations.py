import asyncio
import sys
import os
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.market_memory import MarketMemory
from app.services.news_classifier import NewsClassifier

def is_korean(text):
    if not text: return False
    return len(re.findall(r'[가-힣]', text)) > 3

def sanitize_meta(meta):
    for k, v in meta.items():
        if v is None:
            meta[k] = ""
    return meta

async def main():
    memory = MarketMemory()
    classifier = NewsClassifier()
    
    all_data = memory._collection.get()
    
    if not all_data or not all_data['ids']:
        return
        
    ids = all_data['ids']
    metadatas = all_data['metadatas']
    documents = all_data['documents']
    
    eng_ids = []
    eng_articles = []
    
    for i, _id in enumerate(ids):
        meta = metadatas[i]
        doc = documents[i]
        title = meta.get('title', '')
        
        if not is_korean(title):
            tt = meta.get('translated_title')
            summary = meta.get('impact_summary', '')
            
            needs_reclassify = False
            if not tt or tt == title or not is_korean(tt):
                needs_reclassify = True
            elif not summary or not is_korean(summary):
                needs_reclassify = True
                
            if needs_reclassify:
                eng_ids.append(_id)
                lines = doc.split('\n')
                content = lines[1] if len(lines) > 1 else title
                
                eng_articles.append({
                    "id": _id,
                    "title": title,
                    "content": content,
                    "description": content,
                    "url": meta.get("url", ""),
                    "source": meta.get("source", "Unknown"),
                    "source_name": meta.get("source", "Unknown"),
                    "published_at": meta.get("published_at", ""),
                    "collected_at": meta.get("published_at", ""),
                    "content_snippet": content[:100],
                    "data_source": "chromadb"
                })
                
    if eng_ids:
        print(f"Re-classifying {len(eng_ids)} English articles...")
        for i, _id in enumerate(eng_ids):
            article_dict = eng_articles[i]
            
            print(f"[{i+1}/{len(eng_ids)}] Classifying: {article_dict['content'][:50]}...")
            res = await classifier.classify_article(article_dict)
            if res:
                idx = ids.index(_id)
                meta = metadatas[idx]
                doc = documents[idx]
                
                meta['category'] = res.category
                meta['impact_score'] = res.impact_score
                meta['confidence'] = res.confidence
                meta['translated_title'] = res.translated_title or ""
                meta['impact_summary'] = res.impact_summary or ""
                
                for crude, impact in res.impact_by_crude.items():
                    meta[f"{crude}_score"] = impact.score
                    meta[f"{crude}_direction"] = impact.direction
                    meta[f"{crude}_rationale"] = impact.rationale or ""
                    
                meta = sanitize_meta(meta)
                
                new_doc = f"Title: {res.translated_title or article_dict['title']}\n{article_dict['content']}\nSummary: {res.impact_summary}"
                
                try:
                    memory._collection.update(
                        ids=[_id],
                        metadatas=[meta],
                        documents=[new_doc]
                    )
                    print(f"  -> Success: {res.translated_title}")
                except Exception as e:
                    print(f"  -> Failed to update ChromaDB: {e}")
                
            await asyncio.sleep(2)
            
    print("All fixes completed.")

if __name__ == "__main__":
    asyncio.run(main())
