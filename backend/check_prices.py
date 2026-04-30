import asyncio
from app.core.database import get_session_factory
from sqlalchemy import text
async def main():
    sf = get_session_factory()
    async with sf() as session:
        res = await session.execute(text("SELECT date, source, dubai, wti, brent FROM oil_prices WHERE date='2026-04-20'"))
        for r in res:
            print(dict(r._mapping))
asyncio.run(main())
