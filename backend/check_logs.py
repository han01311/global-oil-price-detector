import asyncio
from app.core.database import Database
async def main():
    db = Database()
    await db.connect()
    res = await db.execute_query('SELECT DISTINCT source, task_type FROM collection_logs')
    print(res)
    await db.close()
asyncio.run(main())
