import asyncio
from app.services.data_collector import EIACollector
async def main():
    eia = EIACollector()
    data = await eia._get_series_data(
        "/petroleum/stoc/wstk/data/", "weekly", 
        eia.SERIES_IDS["inventory"], "2006-01-01", "2026-04-30"
    )
    print(f"Fetched {len(data)} records")
    if data:
        print("First:", data[0].get('period'))
        print("Last:", data[-1].get('period'))
asyncio.run(main())
