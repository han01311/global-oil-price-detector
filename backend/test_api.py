import httpx
import asyncio

async def run():
    async with httpx.AsyncClient() as client:
        r = await client.post('http://localhost:8000/api/news/classify?fetch_latest=true', timeout=120.0)
        print([a.get("impact_by_crude") for a in r.json()][:1])

asyncio.run(run())
