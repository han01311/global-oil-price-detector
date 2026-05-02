import asyncio
from app.api.forecast import _run_forecast_pipeline
from app.models.base import init_db

async def main():
    await init_db()
    res, _, _, data_as_of = await _run_forecast_pipeline()
    print(f"data_as_of: {data_as_of}")
    for crude, fc in res.forecasts_by_crude.items():
        print(f"{crude}: current_price={fc.current_price}")

if __name__ == "__main__":
    asyncio.run(main())
