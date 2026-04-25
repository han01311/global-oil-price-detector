import asyncio
import httpx
from datetime import date, timedelta
from app.core.config import settings

async def test():
    api_key = settings.EIA_API_KEY
    async with httpx.AsyncClient() as client:
        end_date = date.today()
        start_date = end_date - timedelta(days=500)
        # Test inventory
        params = {
            "api_key": api_key,
            "frequency": "weekly",
            "data[0]": "value",
            "facets[series][]": "PET.WCESTUS1.W",
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "sort[0][column]": "period",
            "sort[0][direction]": "asc"
        }
        res = await client.get("https://api.eia.gov/v2/petroleum/stoc/wstk/data/", params=params)
        data = res.json()
        print("Inventory records:", len(data.get("response", {}).get("data", [])))
        
        if len(data.get("response", {}).get("data", [])) > 0:
            print("Sample:", data["response"]["data"][0])

asyncio.run(test())
