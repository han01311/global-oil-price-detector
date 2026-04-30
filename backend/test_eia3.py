import asyncio
from app.services.data_collector import EIACollector
async def main():
    eia = EIACollector()
    params = {
        "api_key": eia.api_key,
        "frequency": "weekly",
        "data[0]": "value",
        "facets[series][]": eia.SERIES_IDS["inventory"],
        "start": "2006-01-01",
        "end": "2026-04-30",
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "offset": 0,
        "length": 5000,
    }
    data = await eia._fetch_api("/petroleum/stoc/wstk/data/", params, "inv")
    print("total records returned:", len(data['response']['data']))
asyncio.run(main())
