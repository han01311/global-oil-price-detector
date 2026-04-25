import asyncio
import httpx
from app.core.config import settings

async def test():
    api_key = settings.EIA_API_KEY
    async with httpx.AsyncClient() as client:
        params = {"api_key": api_key, "length": 1, "data[0]": "value"}
        res = await client.get("https://api.eia.gov/v2/petroleum/stoc/wstk/data/", params=params)
        print("Inventory 1 item:", res.json().get("response", {}).get("data", []))
        
asyncio.run(test())
