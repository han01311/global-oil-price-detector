import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import json

DATABASE_URL = "postgresql+asyncpg://petroax:petroax_dev_2026@localhost:5432/petroax"

async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT id, job_type, status, error_message, results_detail
                FROM pipeline_jobs 
                WHERE id = 'retry-2e90991c528d'
            """)
        )
        row = result.fetchone()
        if row:
            print(f"Job ID: {row[0]}")
            print(f"Status: {row[2]}")
            print(f"Error Message: {row[3]}")
            print(f"Results Detail: {json.dumps(row[4], indent=2, ensure_ascii=False) if row[4] else 'None'}")
        else:
            print("Job not found.")

if __name__ == "__main__":
    asyncio.run(main())
