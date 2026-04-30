import asyncio
from app.core.database import get_session_factory
from sqlalchemy import text

async def main():
    sf = get_session_factory()
    async with sf() as session:
        # Check duplicate dates in oil_prices
        res = await session.execute(text("SELECT date, COUNT(*) as cnt FROM oil_prices GROUP BY date HAVING COUNT(*) > 1"))
        print("oil_prices duplicates:", [dict(r._mapping) for r in res])
        
        # Check duplicate dates in oil_inventory
        res = await session.execute(text("SELECT date, COUNT(*) as cnt FROM oil_inventory GROUP BY date HAVING COUNT(*) > 1"))
        print("oil_inventory duplicates:", [dict(r._mapping) for r in res])

        # Check duplicate dates in oil_production
        res = await session.execute(text("SELECT date, COUNT(*) as cnt FROM oil_production GROUP BY date HAVING COUNT(*) > 1"))
        print("oil_production duplicates:", [dict(r._mapping) for r in res])

        # Check duplicate dates in macro_indicators
        res = await session.execute(text("SELECT date, COUNT(*) as cnt FROM macro_indicators GROUP BY date HAVING COUNT(*) > 1"))
        print("macro_indicators duplicates:", [dict(r._mapping) for r in res])
asyncio.run(main())
