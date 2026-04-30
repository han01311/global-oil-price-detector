import asyncio
from app.core.database import get_session_factory
from sqlalchemy import text

async def main():
    sf = get_session_factory()
    async with sf() as session:
        # Check if fed_rate has nulls and dollar_index has values
        res = await session.execute(text("""
            SELECT 
                COUNT(*) as total, 
                SUM(CASE WHEN fed_rate IS NULL THEN 1 ELSE 0 END) as fed_rate_nulls,
                SUM(CASE WHEN dollar_index IS NULL THEN 1 ELSE 0 END) as dollar_index_nulls
            FROM macro_indicators
        """))
        print(dict(res.mappings().first()))
        
        # Check a few rows
        res2 = await session.execute(text("SELECT date, fed_rate, dollar_index FROM macro_indicators ORDER BY date DESC LIMIT 10"))
        print("\nRecent rows:")
        for r in res2.mappings():
            print(dict(r))
asyncio.run(main())
