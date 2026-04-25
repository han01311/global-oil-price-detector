import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from typing import List, Dict, Optional

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Add project root to path to allow direct script execution
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from app.services.feature_engineering import FeatureEngineer
from app.services.data_collector import DataCollector
from app.schemas.forecast import ForecastResult, FactorBreakdown, CrudeForecast

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CRUDE_TYPES = ["dubai", "brent", "wti"]


def _resolve_ml_dir() -> Path:
    """Resolve ML artifact directory independent of the process cwd."""
    backend_dir = Path(__file__).resolve().parents[2]
    candidates = [
        backend_dir / "ml",
        backend_dir / "backend" / "ml",
    ]
    for candidate in candidates:
        report = candidate / "training_report.json"
        model_dir = candidate / "models"
        if report.exists() and any(model_dir.glob("xgb_*_7d.joblib")):
            return candidate
    return candidates[0]


class ForecastEngine:
    """XGBoost-based oil price forecasting engine — 유종별 독립 모델 지원."""

    _ML_DIR = _resolve_ml_dir()
    MODEL_DIR = _ML_DIR / "models"
    REPORT_PATH = _ML_DIR / "training_report.json"

    def __init__(self):
        self.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        # Per-crude models: {"wti": {"7d": model, "30d": model}, ...}
        self.models: Dict[str, Dict[str, object]] = {}
        self.training_report = None

    def _model_path(self, crude: str, horizon: str) -> Path:
        return self.MODEL_DIR / f"xgb_{crude}_{horizon}.joblib"

    def _load_models(self):
        """Loads all trained models and training report from disk."""
        if self.REPORT_PATH.exists():
            with open(self.REPORT_PATH, 'r') as f:
                self.training_report = json.load(f)
        else:
            raise FileNotFoundError("Training report not found. Please run the training script first.")

        for crude in CRUDE_TYPES:
            self.models[crude] = {}
            for horizon in ["7d", "30d"]:
                path = self._model_path(crude, horizon)
                if path.exists():
                    self.models[crude][horizon] = joblib.load(path)
                else:
                    # Fallback: try loading legacy WTI-only models
                    legacy_path = self.MODEL_DIR / f"xgb_{horizon}.joblib"
                    if crude == "wti" and legacy_path.exists():
                        self.models[crude][horizon] = joblib.load(legacy_path)
                    else:
                        logging.warning(f"Model not found: {path}. Will skip {crude}/{horizon}.")
                        self.models[crude][horizon] = None

    def _get_feature_cols(self, features_df: pd.DataFrame) -> list:
        """Get feature columns (exclude all target columns)."""
        return [c for c in features_df.columns if not c.startswith("target_")]

    def train(self, features_df: pd.DataFrame) -> dict:
        """Trains models for all crude types and evaluates them."""
        if features_df.empty:
            raise ValueError("Features DataFrame cannot be empty.")

        train, test = FeatureEngineer().split_train_test(features_df)
        feature_cols = self._get_feature_cols(train)

        all_metrics = {}

        for crude in CRUDE_TYPES:
            target_7d = f"target_{crude}_7d"
            target_30d = f"target_{crude}_30d"

            # Skip if target columns don't exist (e.g., missing Dubai data)
            if target_7d not in train.columns or target_30d not in train.columns:
                logging.warning(f"Skipping {crude}: target columns not found in features.")
                continue

            X_train, X_test = train[feature_cols], test[feature_cols]

            # --- 7-day model ---
            y_train_7d, y_test_7d = train[target_7d], test[target_7d]
            model_7d = xgb.XGBRegressor(
                n_estimators=200, max_depth=6, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8, random_state=42,
                early_stopping_rounds=10,
            )
            model_7d.fit(X_train, y_train_7d, eval_set=[(X_test, y_test_7d)], verbose=False)

            # --- 30-day model ---
            y_train_30d, y_test_30d = train[target_30d], test[target_30d]
            model_30d = xgb.XGBRegressor(
                n_estimators=200, max_depth=6, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8, random_state=42,
                early_stopping_rounds=10,
            )
            model_30d.fit(X_train, y_train_30d, eval_set=[(X_test, y_test_30d)], verbose=False)

            # --- Save models ---
            joblib.dump(model_7d, self._model_path(crude, "7d"))
            joblib.dump(model_30d, self._model_path(crude, "30d"))

            # --- Evaluation ---
            preds_7d = model_7d.predict(X_test)
            preds_30d = model_30d.predict(X_test)

            all_metrics[crude] = {
                "rmse_7d": float(np.sqrt(mean_squared_error(y_test_7d, preds_7d))),
                "mae_7d": float(mean_absolute_error(y_test_7d, preds_7d)),
                "rmse_30d": float(np.sqrt(mean_squared_error(y_test_30d, preds_30d))),
                "mae_30d": float(mean_absolute_error(y_test_30d, preds_30d)),
            }

            logging.info(f"[{crude.upper()}] RMSE_7d={all_metrics[crude]['rmse_7d']:.4f}, RMSE_30d={all_metrics[crude]['rmse_30d']:.4f}")

        # Feature importance from WTI 7d model (primary)
        wti_7d_path = self._model_path("wti", "7d")
        feature_importance_map = {}
        if wti_7d_path.exists():
            wti_model = joblib.load(wti_7d_path)
            importances = wti_model.feature_importances_
            for col, imp in sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True):
                feature_importance_map[col] = float(imp)

        # Legacy compatibility: top-level metrics use WTI
        wti_metrics = all_metrics.get("wti", {})

        return {
            "rmse_7d": wti_metrics.get("rmse_7d", 0),
            "mae_7d": wti_metrics.get("mae_7d", 0),
            "rmse_30d": wti_metrics.get("rmse_30d", 0),
            "mae_30d": wti_metrics.get("mae_30d", 0),
            "metrics_by_crude": all_metrics,
            "feature_columns": feature_cols,
            "feature_importance": dict(feature_importance_map),
            "data_range": {
                "start": features_df.index.min().strftime('%Y-%m-%d'),
                "end": features_df.index.max().strftime('%Y-%m-%d')
            },
            "samples": len(features_df)
        }

    def predict(self, current_features: pd.DataFrame, crude_type: str = "wti") -> dict:
        """Predicts price changes for a specific crude type."""
        if not self.models:
            self._load_models()

        # Ensure columns are in the same order as during training
        feature_cols = self.training_report.get('feature_columns')
        if feature_cols:
            current_features = current_features[feature_cols]

        crude_models = self.models.get(crude_type, {})
        model_7d = crude_models.get("7d")
        model_30d = crude_models.get("30d")

        # Fallback to WTI models if specific crude model not available
        if model_7d is None:
            model_7d = self.models.get("wti", {}).get("7d")
        if model_30d is None:
            model_30d = self.models.get("wti", {}).get("30d")

        if model_7d is None or model_30d is None:
            raise FileNotFoundError(f"Models for {crude_type} not found.")

        pred_7d = model_7d.predict(current_features)[0]
        pred_30d = model_30d.predict(current_features)[0]

        # Get RMSE from report
        metrics_by_crude = self.training_report.get("metrics_by_crude", {})
        crude_metrics = metrics_by_crude.get(crude_type, {})

        return {
            "baseline_change_7d": float(pred_7d),
            "baseline_change_30d": float(pred_30d),
            "model_rmse_7d": crude_metrics.get("rmse_7d", self.training_report.get("rmse_7d")),
            "model_rmse_30d": crude_metrics.get("rmse_30d", self.training_report.get("rmse_30d")),
        }


class NewsAdjuster:
    """뉴스 기반 유가 보정 로직 — 유종별 독립 보정 지원"""

    async def calculate_adjustment(self, classified_articles: List[Dict],
                                    similar_events: List[Dict],
                                    crude_type: str = "wti") -> Dict:
        """뉴스 분석 결과를 기반으로 특정 유종의 보정값 산출"""
        relevant_articles = [a for a in classified_articles if a.get("is_relevant")]
        
        # 1. 유종별 뉴스 감성 점수 계산
        weighted_score = 0
        article_count = 0
        for a in relevant_articles:
            impact_by_crude = a.get("impact_by_crude", {})
            if crude_type in impact_by_crude:
                crude_impact = impact_by_crude[crude_type]
                # Handle both dict and CrudeImpact model
                if isinstance(crude_impact, dict):
                    score = crude_impact.get("score", 0)
                else:
                    score = crude_impact.score if hasattr(crude_impact, 'score') else 0
                confidence = a.get("confidence", 0.8)
                weighted_score += score * confidence
                article_count += 1
            else:
                # Fallback to overall impact_score
                weighted_score += a.get("impact_score", 0) * a.get("confidence", 0.8)
                article_count += 1

        avg_sentiment = weighted_score / max(article_count, 1)

        # 2. 유사 과거 사례 기반 보정 (유종별)
        similar_adjustment = self._calculate_similar_adjustment(similar_events, crude_type)

        # 3. 최종 보정값 = 감성 기반 + 유사 사례 기반 (가중 결합)
        sentiment_adjustment = self._sentiment_to_pct(avg_sentiment)
        news_adjustment = (
            0.4 * sentiment_adjustment +
            0.6 * similar_adjustment
        )

        # 4. 불확실성
        uncertainty = self._calculate_uncertainty(relevant_articles, crude_type)

        return {
            "news_adjustment_pct": news_adjustment,
            "sentiment_component": avg_sentiment,
            "similar_component": similar_adjustment,
            "uncertainty_factor": uncertainty,
            "article_count": article_count,
            "dominant_category": self._get_dominant_category(relevant_articles, crude_type),
        }

    def _sentiment_to_pct(self, score: float) -> float:
        """감성 스코어(-5~+5)를 변동률(%)로 변환"""
        if score == 0:
            return 0.0
        # 비선형 매핑: score ±1 → ±0.4%, ±3 → ±2.3%, ±5 → ±5%
        return np.sign(score) * (abs(score) / 5) ** 1.5 * 0.05

    def _calculate_similar_adjustment(self, events: List[Dict], crude_type: str = "wti") -> float:
        """유사 사례의 유종별 유가 변동률 가중 평균"""
        total_weight = 0
        weighted_sum = 0
        
        change_key = f"{crude_type}_change_7d"
        fallback_key = "wti_change_7d"
        
        for event in events:
            similarity = event.get("similarity", 0)
            change = event.get(change_key) or event.get(fallback_key)
            
            if change is not None and similarity > 0.5:
                change_decimal = change / 100.0
                weighted_sum += change_decimal * similarity
                total_weight += similarity
                
        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _calculate_uncertainty(self, articles: List[Dict], crude_type: str = "wti") -> float:
        """뉴스 의견 분산으로 불확실성 계산 — 유종별"""
        scores = []
        for a in articles:
            impact_by_crude = a.get("impact_by_crude", {})
            if crude_type in impact_by_crude:
                crude_impact = impact_by_crude[crude_type]
                if isinstance(crude_impact, dict):
                    scores.append(crude_impact.get("score", 0))
                else:
                    scores.append(crude_impact.score if hasattr(crude_impact, 'score') else 0)
            else:
                scores.append(a.get("impact_score", 0))

        if len(scores) < 2:
            return 0.005
        
        std_dev = np.std(scores)
        normalized_std = std_dev / 5.0
        return normalized_std * 0.02

    def _get_dominant_category(self, articles: List[Dict], crude_type: str = "wti") -> Optional[str]:
        """가장 영향력 있는 카테고리 식별 — 유종별"""
        category_impacts = Counter()
        for article in articles:
            category = article.get("category")
            impact_by_crude = article.get("impact_by_crude", {})
            if crude_type in impact_by_crude:
                crude_impact = impact_by_crude[crude_type]
                if isinstance(crude_impact, dict):
                    impact = abs(crude_impact.get("score", 0))
                else:
                    impact = abs(crude_impact.score) if hasattr(crude_impact, 'score') else 0
            else:
                impact = abs(article.get("impact_score", 0))
            if category:
                category_impacts[category] += impact
        
        if not category_impacts:
            return None
        return category_impacts.most_common(1)[0][0]

    def _calculate_factor_breakdown(self, articles: List[Dict], crude_type: str = "wti") -> List[Dict]:
        """카테고리별 기여도 계산 — 유종별"""
        category_contributions = Counter()
        category_counts = Counter()
        total_weighted_score = 0

        for article in articles:
            if not article.get("is_relevant"):
                continue
            impact_by_crude = article.get("impact_by_crude", {})
            if crude_type in impact_by_crude:
                crude_impact = impact_by_crude[crude_type]
                if isinstance(crude_impact, dict):
                    score = crude_impact.get("score", 0)
                else:
                    score = crude_impact.score if hasattr(crude_impact, 'score') else 0
            else:
                score = article.get("impact_score", 0)

            confidence = article.get("confidence", 1.0)
            weighted = score * confidence
            total_weighted_score += weighted

            category = article.get("category")
            if category:
                category_contributions[category] += weighted
                category_counts[category] += 1

        if total_weighted_score == 0:
            return []

        breakdown = []
        sentiment_total_pct = self._sentiment_to_pct(total_weighted_score / max(1, len(articles)))
        
        for category, total_score in category_contributions.items():
            contribution_pct = (total_score / total_weighted_score) * sentiment_total_pct * 0.4
            breakdown.append({
                "category": category,
                "contribution": contribution_pct,
                "article_count": category_counts[category]
            })
        return breakdown


class HybridForecaster:
    """하이브리드 유가 추정기 — 유종별 독립 추정 지원"""

    def __init__(self, engine: ForecastEngine, adjuster: NewsAdjuster):
        self.engine = engine
        self.adjuster = adjuster

    async def forecast(self, current_prices: Dict[str, float],
                       current_features: pd.DataFrame,
                       classified_articles: List[Dict],
                       similar_events: List[Dict]) -> ForecastResult:
        """유종별 독립 추정 밴드 산출"""

        forecasts_by_crude = {}

        for crude in CRUDE_TYPES:
            price = current_prices.get(crude)
            if price is None or pd.isna(price):
                continue

            try:
                baseline = self.engine.predict(current_features, crude_type=crude)
            except FileNotFoundError:
                logging.warning(f"No model for {crude}, skipping.")
                continue

            adjustment = await self.adjuster.calculate_adjustment(
                classified_articles, similar_events, crude_type=crude
            )

            final_change_7d = (1 + baseline["baseline_change_7d"]) * (1 + adjustment["news_adjustment_pct"]) - 1
            estimated_7d = price * (1 + final_change_7d)
            band_7d = baseline["model_rmse_7d"] + adjustment["uncertainty_factor"]

            final_change_30d = (1 + baseline["baseline_change_30d"]) * (1 + adjustment["news_adjustment_pct"]) - 1
            estimated_30d = price * (1 + final_change_30d)
            band_30d = baseline["model_rmse_30d"] + adjustment["uncertainty_factor"]

            forecasts_by_crude[crude] = CrudeForecast(
                crude_type=crude,
                current_price=price,
                estimated_7d=estimated_7d,
                estimated_7d_high=estimated_7d * (1 + band_7d),
                estimated_7d_low=estimated_7d * (1 - band_7d),
                estimated_30d=estimated_30d,
                estimated_30d_high=estimated_30d * (1 + band_30d),
                estimated_30d_low=estimated_30d * (1 - band_30d),
                baseline_change_7d=baseline["baseline_change_7d"],
                baseline_change_30d=baseline["baseline_change_30d"],
                news_adjustment_pct=adjustment["news_adjustment_pct"],
                confidence=max(0, 1 - (band_7d * 2)),
                dominant_factor=adjustment["dominant_category"],
            )

        # Primary result uses WTI for backward compatibility
        wti = forecasts_by_crude.get("wti")
        if wti is None:
            # Use first available crude
            wti = next(iter(forecasts_by_crude.values())) if forecasts_by_crude else None

        if wti is None:
            raise ValueError("No crude type could be forecasted.")

        # Factor breakdown using WTI
        factor_breakdown_data = self.adjuster._calculate_factor_breakdown(
            [a for a in classified_articles if a.get("is_relevant")],
            crude_type="wti"
        )

        wti_adj = await self.adjuster.calculate_adjustment(
            classified_articles, similar_events, crude_type="wti"
        )
        is_extreme = abs(wti_adj["news_adjustment_pct"]) >= 0.05 or wti.confidence < 0.3

        return ForecastResult(
            current_price=wti.current_price,
            estimated_7d=wti.estimated_7d,
            estimated_7d_high=wti.estimated_7d_high,
            estimated_7d_low=wti.estimated_7d_low,
            estimated_30d=wti.estimated_30d,
            estimated_30d_high=wti.estimated_30d_high,
            estimated_30d_low=wti.estimated_30d_low,
            baseline_change_7d=wti.baseline_change_7d,
            baseline_change_30d=wti.baseline_change_30d,
            news_adjustment_pct=wti.news_adjustment_pct,
            confidence=wti.confidence,
            dominant_factor=wti.dominant_factor,
            extreme_volatility_warning=is_extreme,
            factor_breakdown=[FactorBreakdown(**fb) for fb in factor_breakdown_data],
            forecasts_by_crude=forecasts_by_crude,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )


async def run_training():
    """The main training pipeline script."""
    logging.info("Starting model training pipeline...")

    # 1. Data Collection
    logging.info("Collecting historical data...")
    collector = DataCollector()
    end_date = datetime.now()
    start_date = end_date - pd.DateOffset(years=5)
    
    prices_history = await collector.collect_prices(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    macro_history = await collector.collect_macro_data(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    
    prices_df = pd.DataFrame([p.model_dump() for p in prices_history.prices])
    macro_df = pd.DataFrame([i.model_dump() for i in macro_history.indicators])
    
    if prices_df.empty or macro_df.empty:
        logging.error("Failed to collect sufficient data for training.")
        return

    # 2. Feature Engineering
    logging.info("Building features...")
    feature_engineer = FeatureEngineer()
    features_df = feature_engineer.build_features(prices_df, macro_df)

    # 3. Model Training
    logging.info("Training XGBoost models for all crude types...")
    engine = ForecastEngine()
    metrics = engine.train(features_df)

    # 4. Save Report
    logging.info("Saving training report...")
    report = {
        "trained_at": datetime.now().isoformat(),
        "data_range": f"{metrics['data_range']['start']} ~ {metrics['data_range']['end']}",
        "samples": metrics['samples'],
        "rmse_7d": metrics['rmse_7d'],
        "mae_7d": metrics['mae_7d'],
        "rmse_30d": metrics['rmse_30d'],
        "mae_30d": metrics['mae_30d'],
        "metrics_by_crude": metrics.get('metrics_by_crude', {}),
        "feature_columns": metrics['feature_columns'],
        "top_features": dict(list(metrics['feature_importance'].items())[:10]),
    }

    with open(engine.REPORT_PATH, 'w') as f:
        json.dump(report, f, indent=2)

    logging.info(f"Training complete. Report saved to {engine.REPORT_PATH}")
    for crude, m in metrics.get('metrics_by_crude', {}).items():
        logging.info(f"[{crude.upper()}] RMSE_7d={m['rmse_7d']:.4f}, RMSE_30d={m['rmse_30d']:.4f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Forecast Engine Training Script")
    parser.add_argument("--train", action="store_true", help="Run the model training pipeline.")
    args = parser.parse_args()

    if args.train:
        import asyncio
        asyncio.run(run_training())
    else:
        print("Use --train flag to run the training pipeline.")
