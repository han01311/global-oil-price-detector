from fastapi import APIRouter, Query, HTTPException
from datetime import date, timedelta
from app.services.data_collector import DataCollector
from app.schemas.price import PriceHistory, OilPrice, MacroHistory

router = APIRouter(prefix="/api/prices", tags=["prices"])

@router.get("/history", response_model=PriceHistory)
async def get_price_history(
    start_date: str = Query(..., description="시작일 YYYY-MM-DD", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str = Query(..., description="종료일 YYYY-MM-DD", pattern=r"^\d{4}-\d{2}-\d{2}$"),
) -> PriceHistory:
    """WTI/Brent 일별 유가 이력 조회"""
    try:
        collector = DataCollector()
        price_data = await collector.collect_prices(start_date, end_date)
        return price_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/latest", response_model=OilPrice)
async def get_latest_prices() -> OilPrice:
    """최신 유가 조회"""
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=10) # 최근 10일치 데이터 조회
        
        collector = DataCollector()
        price_history = await collector.collect_prices(start_date.isoformat(), end_date.isoformat())
        
        if not price_history.prices:
            raise HTTPException(status_code=404, detail="No recent price data found.")
            
        # 가장 최신 데이터 반환 (prices는 날짜순으로 정렬되어 있다고 가정)
        latest_price = price_history.prices[-1]
        return latest_price
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/macro", response_model=MacroHistory)
async def get_macro_indicators(
    start_date: str = Query(..., description="시작일 YYYY-MM-DD", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str = Query(..., description="종료일 YYYY-MM-DD", pattern=r"^\d{4}-\d{2}-\d{2}$"),
) -> MacroHistory:
    """거시경제 지표 조회"""
    try:
        collector = DataCollector()
        macro_data = await collector.collect_macro_data(start_date, end_date)
        return macro_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
