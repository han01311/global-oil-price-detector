import asyncio
from datetime import date, timedelta
from app.services.data_collector import DataCollector
from app.core.database import Database

async def main():
    collector = DataCollector()
    await collector.db.connect()
    
    end_date = date.today()
    start_date = end_date - timedelta(days=100)
    
    print("Collecting FRED macro data...")
    res = await collector.collect_macro_data(start_date.isoformat(), end_date.isoformat())
    print(f"Collected {len(res.indicators)} macro rows.")

asyncio.run(main())
