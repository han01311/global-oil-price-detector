from fastapi import APIRouter, Query, HTTPException
import asyncio
import pandas as pd
import os
import json
import logging
import time

from app.services.data_collector import DataCollector
from app.services.news_classifier import NewsClassifier
from app.services.market_memory import MarketMemory
from app.services.forecast_engine import HybridForecaster, ForecastEngine, NewsAdjuster, CRUDE_TYPES
from app.services.feature_engineering import FeatureEngineer
from app.services.fundamental_forecast import FundamentalForecastEngine
from app.schemas.forecast import (
    ForecastResult, DualForecastResult, FundamentalForecastResult,
    FundamentalCrudeForecast, FundamentalSignal
)
from app.api.news import _news_cache

router = APIRouter(prefix="/api/forecast", tags=["forecast"])

_forecast_cache = {"data": None, "expires_at": 0}
_forecast_cache_lock = asyncio.Lock()
logger = logging.getLogger(__name__)

async def _run_forecast_pipeline():
    try:
        # 1. Collect data
        collector = DataCollector()
        prices_df = await collector.collect_prices_df_for_features()
        if prices_df.empty:
            raise HTTPException(status_code=404, detail="Could not fetch latest price data.")
            
        # Extract current prices for all crude types
        latest_row = prices_df.iloc[-1]
        current_prices = {}
        for crude in CRUDE_TYPES:
            if crude in latest_row and not pd.isna(latest_row[crude]):
                current_prices[crude] = float(latest_row[crude])

        if not current_prices:
            raise HTTPException(status_code=404, detail="No valid crude prices found in the latest data.")

        # Extract data_as_of: the actual last date in the price data
        # prices_df has 'date' as a column (not index), so use the column directly
        if 'date' in prices_df.columns:
            data_as_of = str(prices_df['date'].max())
        else:
            # fallback: if date is the index (e.g. after set_index)
            idx_max = prices_df.index.max()
            data_as_of = str(idx_max.date()) if hasattr(idx_max, 'date') else ""

        macro_df = await collector.collect_macro_df_for_features()

        # 2. Feature Engineering
        feature_engineer = FeatureEngineer()
        features_df = feature_engineer.build_features(prices_df, macro_df, include_targets=False)
        if features_df.empty:
            raise HTTPException(status_code=404, detail="Could not build forecast features from available data.")
        current_features = features_df.tail(1)

        # 3. News Analysis
        # Forecast is on the critical UI path. Do not trigger live LLM classification here;
        # use cached classified news when available and fall back to a quantitative-only forecast.
        cached_articles = []
        current_time = time.time()
        if _news_cache["data"] is not None and current_time < _news_cache["expires_at"]:
            cached_articles = _news_cache["data"]

        relevant_articles = [
            a.model_dump() if hasattr(a, "model_dump") else a
            for a in cached_articles
            if getattr(a, "is_relevant", False) or (isinstance(a, dict) and a.get("is_relevant"))
        ]

        # 4. Market Memory Search (per-crude if available)
        memory = MarketMemory()
        similar_events = []
        if relevant_articles and memory.is_available():
            most_impactful_article = max(relevant_articles, key=lambda x: abs(x['impact_score']))
            query_text = most_impactful_article['article']['title']
            search_results = await memory.search_similar(query=query_text, n_results=5)
            
            for res in search_results:
                metadata = res.get('metadata', {})
                def get_change(key):
                    val = metadata.get(key)
                    # ChromaDB stores None as -9999.0 sentinel value
                    if val is None or val == -1.0 or val == -9999.0 or val <= -9990:
                        return None
                    return val
                
                event = {
                    "title": res.get('document', '').split('\n')[0].replace('Title: ', ''),
                    "similarity": 1.0 - res.get('distance', 1.0),
                    "wti_change_7d": get_change('wti_change_7d'),
                    "dubai_change_7d": get_change('dubai_change_7d'),
                    "brent_change_7d": get_change('brent_change_7d'),
                }
                similar_events.append(event)

        # 5. Hybrid Forecast (multi-crude)
        engine = ForecastEngine()
        adjuster = NewsAdjuster()
        forecaster = HybridForecaster(engine, adjuster)
        forecast_result = await forecaster.forecast(
            current_prices=current_prices,
            current_features=current_features,
            classified_articles=relevant_articles,
            similar_events=similar_events,
            data_as_of=data_as_of,
        )
        return forecast_result, relevant_articles, similar_events, data_as_of

    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=f"Model not trained yet. Please train the model first. Details: {e}")
    except Exception as e:
        logger.exception("Error in forecast pipeline")
        raise HTTPException(status_code=500, detail=f"An error occurred during forecast generation: {str(e)}")


@router.get("/estimate", response_model=ForecastResult)
async def get_price_estimate(
    crude_type: str = Query(default=None, description="특정 유종 필터 (dubai, brent, wti)"),
) -> ForecastResult:
    """
    현재 유가 추정 결과 조회
    - XGBoost baseline + 뉴스 보정이 결합된 최종 추정
    - 7일/30일 예측 밴드 포함
    - forecasts_by_crude에 유종별 독립 예측 포함
    """
    current_time = time.time()
    if _forecast_cache["data"] is not None and current_time < _forecast_cache["expires_at"]:
        return _forecast_cache["data"]

    async with _forecast_cache_lock:
        current_time = time.time()
        if _forecast_cache["data"] is not None and current_time < _forecast_cache["expires_at"]:
            return _forecast_cache["data"]
        
        forecast_result, _, _, _ = await _run_forecast_pipeline()

        _forecast_cache["data"] = forecast_result
        _forecast_cache["expires_at"] = time.time() + 3600
        return forecast_result

@router.get("/baseline", response_model=dict)
async def get_baseline_only(
    horizon: str = Query(default="7d", pattern="^(7d|30d)$"),
    crude_type: str = Query(default="wti", description="유종 타입 (dubai, brent, wti)"),
) -> dict:
    """XGBoost 베이스라인만 조회 (뉴스 보정 제외) — 유종별"""
    try:
        collector = DataCollector()
        prices_df = await collector.collect_prices_df_for_features()
        macro_df = await collector.collect_macro_df_for_features()
        
        feature_engineer = FeatureEngineer()
        features_df = feature_engineer.build_features(prices_df, macro_df, include_targets=False)
        if features_df.empty:
            raise HTTPException(status_code=404, detail="Could not build forecast features from available data.")
        current_features = features_df.tail(1)
        
        price_col = f"{crude_type}_price"
        if price_col not in current_features.columns:
            raise HTTPException(status_code=400, detail=f"Price data not available for {crude_type}")
        current_price = current_features[price_col].iloc[0]

        engine = ForecastEngine()
        predictions = engine.predict(current_features, crude_type=crude_type)
        
        baseline_change = predictions[f'baseline_change_{horizon}']
        estimated_price = current_price * (1 + baseline_change)

        return {
            "crude_type": crude_type,
            "current_price": current_price,
            "horizon": horizon,
            "baseline_change_pct": baseline_change * 100,
            "estimated_baseline_price": estimated_price,
            "model_rmse": predictions[f'model_rmse_{horizon}']
        }
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Model not trained yet.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-info", response_model=dict)
async def get_model_info() -> dict:
    """모델 정보 조회 (학습 날짜, RMSE, 피처 중요도)"""
    engine = ForecastEngine()
    report_path = engine.REPORT_PATH
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="Model report not found. Please train the model first.")
    
    with open(report_path, 'r') as f:
        report = json.load(f)
    
    return report


_dual_forecast_cache = {"data": None, "expires_at": 0}
_dual_forecast_cache_lock = asyncio.Lock()


@router.get("/dual", response_model=DualForecastResult)
async def get_dual_forecast() -> DualForecastResult:
    """이중 방법론 비교 예측 결과 조회.

    Method A: 기술적 분석 (XGBoost + 뉴스 보정)
    Method B: 펀더멘탈 분석 (수급 기반)
    """
    current_time = time.time()
    if _dual_forecast_cache["data"] is not None and current_time < _dual_forecast_cache["expires_at"]:
        return _dual_forecast_cache["data"]

    async with _dual_forecast_cache_lock:
        current_time = time.time()
        if _dual_forecast_cache["data"] is not None and current_time < _dual_forecast_cache["expires_at"]:
            return _dual_forecast_cache["data"]

        try:
            # Method A: 기존 Hybrid Forecast
            method_a_result, _, _, data_as_of = await _run_forecast_pipeline()

            # Method B: 펀더멘탈 분석
            # Method A의 current_prices를 재사용
            current_prices = {}
            for crude, cf in method_a_result.forecasts_by_crude.items():
                current_prices[crude] = cf.current_price

            fundamental_engine = FundamentalForecastEngine()
            raw_b = await fundamental_engine.forecast(current_prices)

            # raw dict → Pydantic 모델로 변환
            b_forecasts = {}
            for crude, data in raw_b.get("forecasts_by_crude", {}).items():
                signals = [FundamentalSignal(**s) for s in data.get("signals", [])]
                b_forecasts[crude] = FundamentalCrudeForecast(
                    crude_type=data["crude_type"],
                    current_price=data["current_price"],
                    estimated_7d=data["estimated_7d"],
                    estimated_7d_high=data["estimated_7d_high"],
                    estimated_7d_low=data["estimated_7d_low"],
                    total_change_pct=data["total_change_pct"],
                    signals=signals,
                    confidence=data["confidence"],
                )

            method_b_result = FundamentalForecastResult(
                forecasts_by_crude=b_forecasts,
                method="fundamental",
                generated_at=raw_b.get("generated_at", ""),
            )

            # Consensus: WTI 기준으로 두 방법론이 같은 방향인지 확인
            consensus = False
            a_wti = method_a_result.forecasts_by_crude.get("wti")
            b_wti = b_forecasts.get("wti")
            if a_wti and b_wti:
                a_direction = a_wti.estimated_7d - a_wti.current_price
                b_direction = b_wti.estimated_7d - b_wti.current_price
                consensus = (a_direction > 0) == (b_direction > 0)

            from datetime import datetime, timezone
            dual_result = DualForecastResult(
                method_a=method_a_result,
                method_b=method_b_result,
                consensus=consensus,
                data_as_of=data_as_of,
                generated_at=datetime.now(timezone.utc).isoformat(),
            )

            _dual_forecast_cache["data"] = dual_result
            _dual_forecast_cache["expires_at"] = time.time() + 3600

            return dual_result

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Error in dual forecast pipeline")
            raise HTTPException(status_code=500, detail=f"Dual forecast error: {str(e)}")

