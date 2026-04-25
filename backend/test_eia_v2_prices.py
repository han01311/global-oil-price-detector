import asyncio
import httpx
from app.core.config import settings

async def test():
    api_key = settings.EIA_API_KEY
    async with httpx.AsyncClient() as client:
        params = {"api_key": api_key, "length": 1, "data[0]": "value", "facets[series][]": "PET.RWTC.D"}
        res = await client.get("https://api.eia.gov/v2/petroleum/pri/spt/data/", params=params)
        print("WTI PET.RWTC.D:", res.json().get("response", {}).get("data", []))
        
        params["facets[series][]"] = "RWTC"
        res = await client.get("https://api.eia.gov/v2/petroleum/pri/spt/data/", params=params)
        print("WTI RWTC:", res.json().get("response", {}).get("data", []))
        
asyncio.run(test())
