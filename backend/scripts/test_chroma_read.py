import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.market_memory import MarketMemory

memory = MarketMemory()
all_data = memory._collection.get()
metas = all_data['metadatas']
if metas:
    print(metas[0])
