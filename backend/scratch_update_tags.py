import asyncio
from app.services.market_memory import MarketMemory

async def main():
    memory = MarketMemory()
    results = memory._collection.get(limit=10, include=["metadatas"])
    if not results or not results['ids']: return
    
    for i, meta in enumerate(results['metadatas']):
        if "sub_categories" not in meta or not meta["sub_categories"]:
            meta["sub_categories"] = "지정학적 리스크,원유 재고"
            memory._collection.update(
                ids=[results['ids'][i]],
                metadatas=[meta]
            )
            print(f"Updated {results['ids'][i]}")

if __name__ == "__main__":
    asyncio.run(main())
