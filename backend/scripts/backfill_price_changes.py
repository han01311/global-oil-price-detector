import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.core.database import Database
from app.services.market_memory import MarketMemory

async def main():
    db = Database()
    await db.connect()
    
    memory = MarketMemory()
    if not memory.is_available():
        print("MarketMemory is not available.")
        return
        
    print("Fetching all items from ChromaDB...")
    result = memory._collection.get(include=["metadatas"])
    ids = result.get("ids", [])
    metadatas = result.get("metadatas", [])
    
    print(f"Found {len(ids)} items to process.")
    
    updated_count = 0
    for doc_id, metadata in zip(ids, metadatas):
        date_str = metadata.get("date")
        if not date_str:
            print(f"Skipping {doc_id} because it has no date metadata.")
            continue
            
        try:
            changes = await db.get_historical_price_changes(date_str)
            # Update metadata
            for key, val in changes.items():
                if val is None:
                    metadata[key] = -9999.0
                else:
                    metadata[key] = val
                
            memory._collection.update(
                ids=[doc_id],
                metadatas=[metadata]
            )
            updated_count += 1
            if updated_count % 50 == 0:
                print(f"Updated {updated_count}/{len(ids)} items...")
        except Exception as e:
            print(f"Error processing {doc_id} on date {date_str}: {e}")
            
    print(f"Successfully backfilled price changes for {updated_count} items in ChromaDB.")

if __name__ == "__main__":
    asyncio.run(main())
