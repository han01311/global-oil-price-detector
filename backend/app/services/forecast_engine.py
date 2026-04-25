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
from app.schemas.forecast import ForecastResult, FactorBreakdown

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ForecastEngine:
    """XGBoost-based oil price forecasting engine."""

    MODEL_DIR = Path("backend/ml/models")
    REPORT_PATH = Path("backend/ml/training_report.json")

    def __init__(self):
        self.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        self.model_7d = None
        self.model_30d = None
        self.training_report = None

    def _load_models(self):
        """Loads the trained models and training report from disk."""
        model_path_7d = self.MODEL_DIR / "xgb_7d.joblib"
        model_path_30d = self.MODEL_DIR / "xgb_30d.joblib"

        if not model_path_7d.exists() or not model_path_30d.exists():
            raise FileNotFoundError("Trained models not found. Please run the training script first.")
        
        if not self.REPORT_PATH.exists():
            raise FileNotFoundError("Training report not found. Please run the training script first.")

        self.model_7d = joblib.load(model_path_7d)
        self.model_30d = joblib.load(model_path_30d)
        with open(self.REPORT_PATH, 'r') as f:
            self.training_report = json.load(f)

    def train(self, features_df: pd.DataFrame) -> dict:
        """Trains the models and evaluates them."""
        if features_df.empty:
            raise ValueError("Features DataFrame cannot be empty.")

        train, test = FeatureEngineer().split_train_test(features_df)

        feature_cols = [c for c in train.columns if not c.startswith("target_")]
        
        # --- 7-day model ---
        X_train, y_train_7d = train[feature_cols], train["target_7d"]
        X_test, y_test_7d = test[feature_cols], test["target_7d"]

        model_7d = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            early_stopping_rounds=10,
        )
        model_7d.fit(X_train, y_train_7d,
                     eval_set=[(X_test, y_test_7d)],
                     verbose=False)

        # --- 30-day model ---
        y_train_30d = train["target_30d"]
        y_test_30d = test["target_30d"]

        model_30d = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            early_stopping_rounds=10,
        )
        model_30d.fit(X_train, y_train_30d,
                      eval_set=[(X_test, y_test_30d)],
                      verbose=False)

        # --- Save models ---
        joblib.dump(model_7d, self.MODEL_DIR / "xgb_7d.joblib")
        joblib.dump(model_30d, self.MODEL_DIR / "xgb_30d.joblib")

        # --- Evaluation ---
        preds_7d = model_7d.predict(X_test)
        preds_30d = model_30d.predict(X_test)

        rmse_7d = float(np.sqrt(mean_squared_error(y_test_7d, preds_7d)))
        mae_7d = float(mean_absolute_error(y_test_7d, preds_7d))
        rmse_30d = float(np.sqrt(mean_squared_error(y_test_30d, preds_30d)))
        mae_30d = float(mean_absolute_error(y_test_30d, preds_30d))

        # --- Feature Importance ---
        importances = model_7d.feature_importances_
        feature_importance_map = {}
        for col, imp in sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True):
            feature_importance_map[col] = float(imp)

        return {
            "rmse_7d": rmse_7d,
            "mae_7d": mae_7d,
            "rmse_30d": rmse_30d,
            "mae_30d": mae_30d,
            "feature_columns": feature_cols,
            "feature_importance": dict(feature_importance_map),
            "data_range": {
                "start": features_df.index.min().strftime('%Y-%m-%d'),
                "end": features_df.index.max().strftime('%Y-%m-%d')
            },
            "samples": len(features_df)
        }

    def predict(self, current_features: pd.DataFrame) -> dict:
        """Predicts price changes based on current features."""
        if self.model_7d is None or self.training_report is None:
            self._load_models()

        # Ensure columns are in the same order as during training
        feature_cols = self.training_report.get('feature_columns')
        if feature_cols:
            current_features = current_features[feature_cols]

        pred_7d = self.model_7d.predict(current_features)[0]
        pred_30d = self.model_30d.predict(current_features)[0]

        return {
            "baseline_change_7d": float(pred_7d),
            "baseline_change_30d": float(pred_30d),
            "model_rmse_7d": self.training_report.get("rmse_7d"),
            "model_rmse_30d": self.training_report.get("rmse_30d"),
        }

class NewsAdjuster:
    """뉴스 기반 유가 보정 로직"""

    async def calculate_adjustment(self, classified_articles: List[Dict],
                                    similar_events: List[Dict]) -> Dict:
        """뉴스 분석 결과를 기반으로 보정값 산출"""
        relevant_articles = [a for a in classified_articles if a.get("is_relevant")]
        
        # 1. 현재 뉴스 기반 종합 감성
        weighted_score = sum(
            a["impact_score"] * a["confidence"]
            for a in relevant_articles
        )
        article_count = len(relevant_articles)
        avg_sentiment = weighted_score / max(article_count, 1)

        # 2. 유사 과거 사례 기반 보정
        similar_adjustment = self._calculate_similar_adjustment(similar_events)

        # 3. 최종 보정값 = 감성 기반 + 유사 사례 기반 (가중 결합)
        sentiment_adjustment = self._sentiment_to_pct(avg_sentiment)
        news_adjustment = (
            0.4 * sentiment_adjustment +
            0.6 * similar_adjustment
        )

        # 4. 불확실성 (뉴스 분산이 크면 신뢰구간 넓힘)
        uncertainty = self._calculate_uncertainty(relevant_articles)

        return {
            "news_adjustment_pct": news_adjustment,
            "sentiment_component": avg_sentiment,
            "similar_component": similar_adjustment,
            "uncertainty_factor": uncertainty,
            "article_count": article_count,
            "dominant_category": self._get_dominant_category(relevant_articles),
        }

    def _sentiment_to_pct(self, score: float) -> float:
        """감성 스코어(-5~+5)를 변동률(%)로 변환"""
        if score == 0:
            return 0.0
        # 비선형 매핑: score ±1 → ±0.4%, ±3 → ±2.3%, ±5 → ±5%
        return np.sign(score) * (abs(score) / 5) ** 1.5 * 0.05

    def _calculate_similar_adjustment(self, events: List[Dict]) -> float:
        """유사 사례의 유가 변동률 가중 평균"""
        total_weight = 0
        weighted_sum = 0
        
        for event in events:
            similarity = event.get("similarity", 0)
            # Use 7-day change as it's more stable than 1-day
            change = event.get("wti_change_7d")
            
            if change is not None and similarity > 0.5: # Use a similarity threshold
                change_decimal = change / 100.0
                weighted_sum += change_decimal * similarity
                total_weight += similarity
                
        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _calculate_uncertainty(self, articles: List[Dict]) -> float:
        """뉴스 의견 분산으로 불확실성 계산"""
        relevant_scores = [a["impact_score"] for a in articles]
        if len(relevant_scores) < 2:
            return 0.005  # Base uncertainty for few articles
        
        std_dev = np.std(relevant_scores)
        normalized_std = std_dev / 5.0  # Max score is 5
        
        # Map to a small percentage for the confidence band, e.g., 0% to 2%
        uncertainty_pct = normalized_std * 0.02
        return uncertainty_pct

    def _get_dominant_category(self, articles: List[Dict]) -> Optional[str]:
        """가장 영향력 있는 카테고리 식별"""
        category_impacts = Counter()
        for article in articles:
            category = article.get("category")
            impact = article.get("impact_score", 0)
            if category:
                category_impacts[category] += abs(impact)
        
        if not category_impacts:
            return None
        
        return category_impacts.most_common(1)[0][0]

    def _calculate_factor_breakdown(self, articles: List[Dict]) -> List[Dict]:
        """카테고리별 기여도 계산"""
        category_contributions = Counter()
        category_counts = Counter()
        total_weighted_score = sum(a["impact_score"] * a["confidence"] for a in articles if a.get("is_relevant"))

        if total_weighted_score == 0:
            return []

        for article in articles:
            if article.get("is_relevant"):
                category = article.get("category")
                weighted_score = article.get("impact_score", 0) * article.get("confidence", 1.0)
                if category:
                    category_contributions[category] += weighted_score
                    category_counts[category] += 1
        
        breakdown = []
        sentiment_total_pct = self._sentiment_to_pct(total_weighted_score / max(1, len(articles)))
        
        for category, total_score in category_contributions.items():
            # Approximate contribution based on its share of the total score
            contribution_pct = (total_score / total_weighted_score) * sentiment_total_pct * 0.4 # 0.4 sentiment weight
            breakdown.append({
                "category": category,
                "contribution": contribution_pct,
                "article_count": category_counts[category]
            })
        return breakdown


class HybridForecaster:
    """하이브리드 유가 추정기 (XGBoost + 뉴스 보정)"""

    def __init__(self, engine: ForecastEngine, adjuster: NewsAdjuster):
        self.engine = engine
        self.adjuster = adjuster

    async def forecast(self, current_price: float, current_features: pd.DataFrame,
                       classified_articles: List[Dict], similar_events: List[Dict]) -> ForecastResult:
        """최종 유가 추정 밴드 산출"""
        # 1. XGBoost baseline
        baseline = self.engine.predict(current_features)

        # 2. News adjustment
        adjustment = await self.adjuster.calculate_adjustment(classified_articles, similar_events)

        # 3. Final calculation (7d)
        final_change_7d = (1 + baseline["baseline_change_7d"]) * (1 + adjustment["news_adjustment_pct"]) - 1
        estimated_price_7d = current_price * (1 + final_change_7d)

        # 4. Confidence band (7d)
        band_width_7d = baseline["model_rmse_7d"] + adjustment["uncertainty_factor"]

        # 5. Final calculation (30d)
        final_change_30d = (1 + baseline["baseline_change_30d"]) * (1 + adjustment["news_adjustment_pct"]) - 1
        estimated_price_30d = current_price * (1 + final_change_30d)

        # 6. Confidence band (30d)
        band_width_30d = baseline["model_rmse_30d"] + adjustment["uncertainty_factor"]

        # 7. Factor breakdown
        factor_breakdown_data = self.adjuster._calculate_factor_breakdown(
            [a for a in classified_articles if a.get("is_relevant")]
        )

        # 8. Black Swan Detection
        is_extreme = abs(adjustment["news_adjustment_pct"]) >= 0.05 or band_width_7d >= 0.1

        return ForecastResult(
            current_price=current_price,
            estimated_7d=estimated_price_7d,
            estimated_7d_high=estimated_price_7d * (1 + band_width_7d),
            estimated_7d_low=estimated_price_7d * (1 - band_width_7d),
            estimated_30d=estimated_price_30d,
            estimated_30d_high=estimated_price_30d * (1 + band_width_30d),
            estimated_30d_low=estimated_price_30d * (1 - band_width_30d),
            baseline_change_7d=baseline["baseline_change_7d"],
            baseline_change_30d=baseline["baseline_change_30d"],
            news_adjustment_pct=adjustment["news_adjustment_pct"],
            confidence=max(0, 1 - (band_width_7d * 2)),
            dominant_factor=adjustment["dominant_category"],
            extreme_volatility_warning=is_extreme,
            factor_breakdown=[FactorBreakdown(**fb) for fb in factor_breakdown_data],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

async def run_training():
    """The main training pipeline script."""
    logging.info("Starting model training pipeline...")

    # 1. Data Collection
    logging.info("Collecting historical data...")
    collector = DataCollector()
    # Collect data for the last 5 years
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
    logging.info("Training XGBoost models...")
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
        "feature_columns": metrics['feature_columns'],
        "top_features": dict(list(metrics['feature_importance'].items())[:10]),
    }

    with open(engine.REPORT_PATH, 'w') as f:
        json.dump(report, f, indent=2)

    logging.info(f"Training complete. Report saved to {engine.REPORT_PATH}")
    logging.info(f"Metrics: RMSE_7d={report['rmse_7d']:.4f}, RMSE_30d={report['rmse_30d']:.4f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Forecast Engine Training Script")
    parser.add_argument("--train", action="store_true", help="Run the model training pipeline.")
    args = parser.parse_args()

    if args.train:
        import asyncio
        asyncio.run(run_training())
    else:
        print("Use --train flag to run the training pipeline.")
