import asyncio
import httpx
from datetime import date, timedelta
from app.core.config import settings

async def test():
    api_key = settings.EIA_API_KEY
    async with httpx.AsyncClient() as client:
        end_date = date.today()
        start_date = end_date - timedelta(days=90)
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
        
        # Test production
        params["facets[series][]"] = "PET.WCRFPUS2.W"
        res = await client.get("https://api.eia.gov/v2/petroleum/sum/sndw/data/", params=params)
        data = res.json()
        print("Production records:", len(data.get("response", {}).get("data", [])))

asyncio.run(test())
