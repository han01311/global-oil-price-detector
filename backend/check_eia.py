import asyncio
from app.core.database import get_session_factory
from sqlalchemy import text

async def main():
    sf = get_session_factory()
    async with sf() as session:
        res = await session.execute(text("SELECT min(date), max(date), count(*) FROM oil_inventory"))
        for r in res:
            print(dict(r._mapping))
asyncio.run(main())
