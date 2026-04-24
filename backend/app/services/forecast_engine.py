import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

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
# The following imports are for the training script part
from app.services.data_collector import DataCollector

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

        rmse_7d = np.sqrt(mean_squared_error(y_test_7d, preds_7d))
        mae_7d = mean_absolute_error(y_test_7d, preds_7d)
        rmse_30d = np.sqrt(mean_squared_error(y_test_30d, preds_30d))
        mae_30d = mean_absolute_error(y_test_30d, preds_30d)

        # --- Feature Importance ---
        importances = model_7d.feature_importances_
        feature_importance_map = sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True)

        return {
            "rmse_7d": rmse_7d,
            "mae_7d": mae_7d,
            "rmse_30d": rmse_30d,
            "mae_30d": mae_30d,
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
        feature_cols = list(self.training_report['top_features'].keys())
        current_features = current_features[feature_cols]

        pred_7d = self.model_7d.predict(current_features)[0]
        pred_30d = self.model_30d.predict(current_features)[0]

        return {
            "baseline_change_7d": float(pred_7d),
            "baseline_change_30d": float(pred_30d),
            "model_rmse_7d": self.training_report.get("rmse_7d"),
            "model_rmse_30d": self.training_report.get("rmse_30d"),
        }

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
