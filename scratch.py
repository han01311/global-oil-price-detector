import asyncio
from datetime import date, timedelta
from app.services.data_collector import DataCollector

async def main():
    collector = DataCollector()
    end_date = date.today()
    start_date = end_date - timedelta(days=100)
    print("Collecting from", start_date, "to", end_date)
    history = await collector.collect_prices(start_date.isoformat(), end_date.isoformat())
    if history and history.prices:
        print("Got prices:", len(history.prices))
        print(history.prices[0])
    else:
        print("Got no prices!")

if __name__ == "__main__":
    asyncio.run(main())
