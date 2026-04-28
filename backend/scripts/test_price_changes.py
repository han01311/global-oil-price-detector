import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.core.database import Database

async def main():
    db = Database()
    await db.connect()
    
    changes = await db.get_historical_price_changes("2023-01-05T12:00:00Z")
    print(changes)

if __name__ == "__main__":
    asyncio.run(main())
