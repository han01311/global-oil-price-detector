import asyncio
from app.core.database import get_session_factory
from sqlalchemy import text

async def main():
    sf = get_session_factory()
    async with sf() as session:
        # Delete all macro indicators
        res = await session.execute(text("DELETE FROM macro_indicators"))
        print(f"Deleted {res.rowcount} macro records")
        await session.commit()
asyncio.run(main())
