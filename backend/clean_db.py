import asyncio
from app.core.database import get_session_factory
from sqlalchemy import text

async def main():
    sf = get_session_factory()
    async with sf() as session:
        # Delete non-opinet prices
        res1 = await session.execute(text("DELETE FROM oil_prices WHERE source != 'opinet'"))
        print(f"Deleted {res1.rowcount} non-opinet prices")
        
        # Now let's see if there are still duplicate dates in macro_indicators
        # Wait, the macro_indicators has a single date with BOTH fed_rate and dollar_index?
        res2 = await session.execute(text("SELECT date, COUNT(*) as cnt FROM macro_indicators GROUP BY date HAVING COUNT(*) > 1"))
        print("macro_indicators duplicates:", [dict(r._mapping) for r in res2])
        
        await session.commit()
asyncio.run(main())
