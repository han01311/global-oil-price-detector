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
        from app.core.database import Database
        from datetime import datetime
        db = Database()
        await db.connect()
        db_rows = await db.get_oil_prices(start_date, end_date, limit=100)
        
        sd = datetime.strptime(start_date, "%Y-%m-%d")
        ed = datetime.strptime(end_date, "%Y-%m-%d")
        expected_trading_days = (ed - sd).days * (5/7) * 0.8
        
        if db_rows and len(db_rows) >= max(1, expected_trading_days):
            # DB returns DESC, we need ASC for charts
            asc_rows = list(reversed(db_rows))
            
            # Forward-fill missing values
            last_valid = {"dubai": None, "wti": None, "brent": None}
            prices = []
            for row in asc_rows:
                d = dict(row)
                for k in ["dubai", "wti", "brent"]:
                    if d.get(k) is not None:
                        last_valid[k] = d[k]
                    else:
                        d[k] = last_valid[k]
                prices.append(OilPrice(**d))
                
            return PriceHistory(prices=prices, source="opinet", last_updated=datetime.now().isoformat())

        collector = DataCollector()
        price_data = await collector.collect_prices(start_date, end_date)
        return price_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/latest", response_model=OilPrice)
async def get_latest_prices() -> OilPrice:
    """최신 유가 조회"""
    try:
        from app.core.database import Database
        db = Database()
        await db.connect()
        
        end_date = date.today()
        start_date = end_date - timedelta(days=10) # 최근 10일치 데이터 조회
        
        db_rows = await db.get_oil_prices(start_date.isoformat(), end_date.isoformat(), limit=10)
        if db_rows:
            # db_rows is DESC (newest first). To find the latest valid price for each, we scan from newest to oldest.
            latest_valid = {"dubai": None, "wti": None, "brent": None}
            for row in db_rows:
                for k in ["dubai", "wti", "brent"]:
                    val = row.get(k)
                    if latest_valid[k] is None and val is not None and val != 0:
                        latest_valid[k] = val
            
            # Combine into a single latest record using the date of the newest row
            latest = dict(db_rows[0])
            for k in ["dubai", "wti", "brent"]:
                latest[k] = latest_valid[k]
                
            return OilPrice(**latest)
            
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
