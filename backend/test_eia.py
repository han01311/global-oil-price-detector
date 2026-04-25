import asyncio
import httpx
from app.core.config import settings

async def test():
    api_key = settings.EIA_API_KEY
    async with httpx.AsyncClient() as client:
        # Test WTI
        params = {
            "api_key": api_key,
            "frequency": "daily",
            "data[0]": "value",
            "facets[series][]": "PET.RWTC.D",
            "start": "2024-01-01",
        }
        res = await client.get("https://api.eia.gov/v2/petroleum/pri/spt/data/", params=params)
        print("WTI Response Status:", res.status_code)
        if res.status_code != 200:
             print(res.text)
             
        # Test inventory
        params = {
            "api_key": api_key,
            "frequency": "weekly",
            "data[0]": "value",
            "facets[series][]": "PET.WCESTUS1.W",
            "start": "2024-01-01",
        }
        res = await client.get("https://api.eia.gov/v2/petroleum/stoc/wstk/data/", params=params)
        print("Inventory Response Status:", res.status_code)
        if res.status_code != 200:
             print(res.text)
        
        # Test production
        params["facets[series][]"] = "PET.WCRFPUS2.W"
        res = await client.get("https://api.eia.gov/v2/petroleum/sum/sndw/data/", params=params)
        print("Production Response Status:", res.status_code)
        if res.status_code != 200:
             print(res.text)

asyncio.run(test())
