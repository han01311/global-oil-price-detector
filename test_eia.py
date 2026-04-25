import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("EIA_API_KEY")

async def test():
    async with httpx.AsyncClient() as client:
        # Test inventory
        params = {
            "api_key": api_key,
            "frequency": "weekly",
            "data[0]": "value",
            "facets[seriesId][]": "PET.WCESTUS1.W",
            "start": "2024-01-01",
        }
        res = await client.get("https://api.eia.gov/v2/petroleum/stoc/wstk/data/", params=params)
        print("Inventory Response Status:", res.status_code)
        if res.status_code != 200:
             print(res.text)
        
        # Test production
        params["facets[seriesId][]"] = "PET.WCRFPUS2.W"
        res = await client.get("https://api.eia.gov/v2/petroleum/sum/sndw/data/", params=params)
        print("Production Response Status:", res.status_code)
        if res.status_code != 200:
             print(res.text)

asyncio.run(test())
