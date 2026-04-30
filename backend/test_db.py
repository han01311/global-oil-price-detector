import asyncio
from app.core.database import Database
async def main():
    db = Database()
    await db.connect()
    
    inv = await db.execute_query("SELECT date, inventory_mbbl, collected_at FROM oil_inventory ORDER BY date DESC LIMIT 5")
    print("EIA Inventory:", [dict(r) for r in inv])
    
    prod = await db.execute_query("SELECT date, production_kbpd, collected_at FROM oil_production ORDER BY date DESC LIMIT 5")
    print("EIA Production:", [dict(r) for r in prod])
    
    mac = await db.execute_query("SELECT date, indicator_code, value FROM macro_indicators ORDER BY date DESC LIMIT 5")
    print("FRED Macro:", [dict(r) for r in mac])
    
    await db.close()

asyncio.run(main())
