from fastapi import APIRouter, Query, HTTPException
import pandas as pd
import os
import json
import logging
import time

from app.services.data_collector import DataCollector
from app.services.news_classifier import NewsClassifier
from app.services.market_memory import MarketMemory
from app.services.forecast_engine import HybridForecaster, ForecastEngine, NewsAdjuster
from app.services.feature_engineering import FeatureEngineer
from app.schemas.forecast import ForecastResult
from app.api.news import classify_news

router = APIRouter(prefix="/api/forecast", tags=["forecast"])

_forecast_cache = {"data": None, "expires_at": 0}
logger = logging.getLogger(__name__)

async def _run_forecast_pipeline():
    try:
        # 1. Collect data
        collector = DataCollector()
        prices_df = await collector.collect_prices_df_for_features()
        if prices_df.empty:
            raise HTTPException(status_code=404, detail="Could not fetch latest price data.")
            
        # prices_df is indexed by date and sorted
        current_price = prices_df.iloc[-1]['wti']
        if pd.isna(current_price):
             raise HTTPException(status_code=404, detail="WTI price is missing in the latest data.")

        macro_df = await collector.collect_macro_df_for_features()

        # 2. Feature Engineering
        feature_engineer = FeatureEngineer()
        features_df = feature_engineer.build_features(prices_df, macro_df)
        current_features = features_df.tail(1)

        # 3. News Analysis (Uses cached results if available)
        classified_articles = await classify_news(articles=None, fetch_latest=True)
        
        relevant_articles = [a.model_dump() for a in classified_articles if a.is_relevant]

        # 4. Market Memory Search
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
                    return None if val == -1.0 else val
                
                event = {
                    "title": res.get('document', '').split('\n')[0].replace('Title: ', ''),
                    "similarity": 1.0 - res.get('distance', 1.0),
                    "wti_change_7d": get_change('wti_change_7d'),
                }
                similar_events.append(event)

        # 5. Hybrid Forecast
        engine = ForecastEngine()
        adjuster = NewsAdjuster()
        forecaster = HybridForecaster(engine, adjuster)
        forecast_result = await forecaster.forecast(
            current_price=current_price,
            current_features=current_features,
            classified_articles=relevant_articles,
            similar_events=similar_events
        )
        return forecast_result, relevant_articles, similar_events

    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=f"Model not trained yet. Please train the model first. Details: {e}")
    except Exception as e:
        logger.exception("Error in forecast pipeline")
        raise HTTPException(status_code=500, detail=f"An error occurred during forecast generation: {str(e)}")


@router.get("/estimate", response_model=ForecastResult)
async def get_price_estimate() -> ForecastResult:
    """
    현재 유가 추정 결과 조회
    - XGBoost baseline + 뉴스 보정이 결합된 최종 추정
    - 7일/30일 예측 밴드 포함
    """
    current_time = time.time()
    if _forecast_cache["data"] is not None and current_time < _forecast_cache["expires_at"]:
        return _forecast_cache["data"]
        
    forecast_result, _, _ = await _run_forecast_pipeline()
    
    _forecast_cache["data"] = forecast_result
    _forecast_cache["expires_at"] = current_time + 3600
    return forecast_result

@router.get("/baseline", response_model=dict)
async def get_baseline_only(
    horizon: str = Query(default="7d", pattern="^(7d|30d)$"),
) -> dict:
    """XGBoost 베이스라인만 조회 (뉴스 보정 제외)"""
    try:
        collector = DataCollector()
        prices_df = await collector.collect_prices_df_for_features()
        macro_df = await collector.collect_macro_df_for_features()
        
        feature_engineer = FeatureEngineer()
        features_df = feature_engineer.build_features(prices_df, macro_df)
        current_features = features_df.tail(1)
        current_price = current_features['wti_price'].iloc[0]

        engine = ForecastEngine()
        predictions = engine.predict(current_features)
        
        baseline_change = predictions[f'baseline_change_{horizon}']
        estimated_price = current_price * (1 + baseline_change)

        return {
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
