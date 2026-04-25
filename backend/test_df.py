import asyncio
from app.services.data_collector import DataCollector

async def test():
    c = DataCollector()
    df = await c.collect_prices_df_for_features()
    print("Columns:", df.columns.tolist())
    print(df.tail(3))

if __name__ == "__main__":
    asyncio.run(test())
