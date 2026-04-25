import asyncio
import httpx
from app.core.config import settings

async def test():
    api_key = settings.EIA_API_KEY
    async with httpx.AsyncClient() as client:
        params = {
            "api_key": api_key,
            "frequency": "weekly",
            "data[0]": "value",
            "facets[series][]": "PET.WCESTUS1.W",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": 5
        }
        res = await client.get("https://api.eia.gov/v2/petroleum/stoc/wstk/data/", params=params)
        data = res.json()
        print("Inventory records:", len(data.get("response", {}).get("data", [])))
        if len(data.get("response", {}).get("data", [])) > 0:
            for item in data["response"]["data"]:
                print(item.get("period"), item.get("value"))

asyncio.run(test())
