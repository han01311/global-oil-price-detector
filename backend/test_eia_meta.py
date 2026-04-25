import asyncio
import httpx
from app.core.config import settings
import json

async def test():
    api_key = settings.EIA_API_KEY
    async with httpx.AsyncClient() as client:
        params = {"api_key": api_key}
        res = await client.get("https://api.eia.gov/v2/petroleum/stoc/wstk/", params=params)
        print("Inventory meta:")
        print(json.dumps(res.json().get("response", {}), indent=2))
        
asyncio.run(test())
