import asyncio
from app.core.database import get_session_factory
from sqlalchemy import text

async def main():
    sf = get_session_factory()
    async with sf() as session:
        res = await session.execute(text("SELECT date, fed_rate, dollar_index FROM macro_indicators ORDER BY date DESC LIMIT 10"))
        for r in res:
            print(dict(r._mapping))
asyncio.run(main())
