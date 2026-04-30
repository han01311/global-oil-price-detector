import asyncio
from app.services.data_collector import DataCollector
async def main():
    collector = DataCollector()
    await collector.db.connect()
    
    df = await collector.collect_macro_df_for_features()
    print("Features DF head:")
    print(df.head())
    print("\nFeatures DF tail:")
    print(df.tail())
asyncio.run(main())
