import asyncio
from app.core.database import get_session_factory
from sqlalchemy import text

async def main():
    sf = get_session_factory()
    async with sf() as session:
        print("=== oil_prices ===")
        res = await session.execute(text("SELECT date, dubai, wti, brent FROM oil_prices ORDER BY date DESC LIMIT 5"))
        for r in res.mappings(): print(dict(r))

        print("\n=== oil_inventory ===")
        res = await session.execute(text("SELECT date, inventory_mbbl FROM oil_inventory ORDER BY date DESC LIMIT 3"))
        for r in res.mappings(): print(dict(r))

        print("\n=== oil_production ===")
        res = await session.execute(text("SELECT date, production_mbbl_d FROM oil_production ORDER BY date DESC LIMIT 3"))
        for r in res.mappings(): print(dict(r))

        print("\n=== macro_indicators ===")
        res = await session.execute(text("SELECT date, fed_rate, dollar_index FROM macro_indicators ORDER BY date DESC LIMIT 3"))
        for r in res.mappings(): print(dict(r))

asyncio.run(main())
