import sys
from pathlib import Path

# Add backend dir to sys.path
sys.path.insert(0, "/Users/jazzmandarine/Documents/GitHub/global-oil-price-detector/backend")

from app.services.market_memory import MarketMemory

if __name__ == "__main__":
    mm = MarketMemory()
    print(f"Path used: {MarketMemory._default_db_path()}")
    print(f"Count: {mm._collection.count()}")
