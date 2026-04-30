import asyncio
import os
import shutil
from datetime import date, timedelta
from app.services.data_collector import EIACollector
from app.core.database import Database

async def main():
    eia = EIACollector()
    db = Database()
    
    # Clear cache to force API call
    if os.path.exists(eia.cache_dir):
        shutil.rmtree(eia.cache_dir)
        os.makedirs(eia.cache_dir)
    
    end_date = date.today()
    start_date = end_date - timedelta(days=365 * 20)
    
    print(f"Fetching EIA data from {start_date} to {end_date}...")
    
    print("1. Fetching Inventory...")
    inv_df = await eia.get_crude_inventory(start_date.isoformat(), end_date.isoformat())
    if not inv_df.empty:
        inv_records = inv_df.to_dict(orient="records")
        count = await db.upsert_oil_inventory(inv_records)
        print(f"Upserted {count} inventory records.")
    else:
        print("No inventory data found.")
        
    print("2. Fetching Production...")
    prod_df = await eia.get_production(start_date.isoformat(), end_date.isoformat())
    if not prod_df.empty:
        prod_records = prod_df.to_dict(orient="records")
        count = await db.upsert_oil_production(prod_records)
        print(f"Upserted {count} production records.")
    else:
        print("No production data found.")

if __name__ == "__main__":
    asyncio.run(main())
