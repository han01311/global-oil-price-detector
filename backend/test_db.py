import asyncio
from app.core.database import Database
from app.services.scheduler import CollectionScheduler

async def test():
    db = Database()
    await db.connect()
    try:
        scheduler = CollectionScheduler()
        await scheduler.start()
        print("Scheduler started successfully")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
