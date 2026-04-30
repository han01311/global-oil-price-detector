import asyncio
from app.core.database import get_session_factory
from sqlalchemy import text

async def main():
    sf = get_session_factory()
    async with sf() as session:
        res = await session.execute(text("SELECT date, fed_rate FROM macro_indicators WHERE fed_rate != 'NaN'"))
        rows = res.fetchall()
        print("Rows with valid fed_rate:", len(rows))
        for r in rows[:5]:
            print(r)
asyncio.run(main())
