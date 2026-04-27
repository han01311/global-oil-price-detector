import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.market_memory import MarketMemory

memory = MarketMemory()
count = memory._collection.count()
print(f"Total articles in ChromaDB: {count}")
