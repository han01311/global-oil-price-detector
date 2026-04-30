import asyncio
from app.core.database import get_session_factory
from sqlalchemy import text

async def main():
    sf = get_session_factory()
    async with sf() as session:
        res = await session.execute(text("SELECT date FROM oil_inventory ORDER BY date"))
        for r in res:
            print(r[0])
asyncio.run(main())
