import asyncio
from datetime import date, timedelta
from app.services.data_collector import DataCollector

async def main():
    collector = DataCollector()
    macro_df = await collector.collect_macro_df_for_features()
    print("macro_df columns:", macro_df.columns)
    print("macro_df empty?", macro_df.empty)

if __name__ == "__main__":
    asyncio.run(main())
