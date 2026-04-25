import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import joblib
import json

from app.services.forecast_engine import ForecastEngine
from app.services.feature_engineering import FeatureEngineer

@pytest.fixture
def sample_features_df():
    """Generates a sample features DataFrame for testing."""
    dates = pd.to_datetime([datetime(2023, 1, 1) + timedelta(days=i) for i in range(150)])
    data = {
        'wti_price': np.linspace(70, 85, 150),
        'brent_price': np.linspace(75, 90, 150),
        'wti_ma5_ratio': np.random.rand(150) + 0.5,
        'dollar_index': np.linspace(100, 105, 150),
        'fed_rate': np.linspace(3.0, 3.5, 150),
        'target_7d': np.random.randn(150) * 0.01,
        'target_30d': np.random.randn(150) * 0.02,
    }
    # Add more dummy features to match expectations
    for i in range(20):
        data[f'dummy_feature_{i}'] = np.random.rand(150)
        
    df = pd.DataFrame(data, index=dates)
    return df

@pytest.fixture
def forecast_engine(tmp_path):
    """Provides a ForecastEngine instance with a temporary path for models."""
    engine = ForecastEngine()
    engine.MODEL_DIR = tmp_path / "models"
    engine.REPORT_PATH = tmp_path / "report.json"
    engine.MODEL_DIR.mkdir()
    return engine

def test_train_saves_models_and_returns_metrics(forecast_engine, sample_features_df):
    """AC 1 & 3 & 4: Test that training saves models, returns metrics, and feature importance."""
    # Act
    metrics = forecast_engine.train(sample_features_df)

    # Assert
    # AC 1: Models are saved
    assert (forecast_engine.MODEL_DIR / "xgb_7d.joblib").exists()
    assert (forecast_engine.MODEL_DIR / "xgb_30d.joblib").exists()

    # AC 3: Metrics are returned
    assert "rmse_7d" in metrics
    assert "mae_7d" in metrics
    assert "rmse_30d" in metrics
    assert "mae_30d" in metrics
    assert isinstance(metrics["rmse_7d"], float)

    # AC 4: Feature importance is returned
    assert "feature_importance" in metrics
    assert isinstance(metrics["feature_importance"], dict)
    assert "wti_price" in metrics["feature_importance"]
    assert len(metrics["feature_importance"]) > 5

def test_predict_loads_models_and_returns_predictions(forecast_engine, sample_features_df):
    """AC 2: Test the full train -> save -> load -> predict flow."""
    # Arrange: Train and save models first
    metrics = forecast_engine.train(sample_features_df)
    
    # Create a dummy report file for the predict method to load
    report = {
        "rmse_7d": metrics['rmse_7d'],
        "rmse_30d": metrics['rmse_30d'],
        "feature_columns": metrics['feature_columns'],
        "top_features": metrics['feature_importance']
    }
    with open(forecast_engine.REPORT_PATH, 'w') as f:
        json.dump(report, f)

    # Get the last row of features for prediction (excluding targets)
    feature_cols = [c for c in sample_features_df.columns if not c.startswith("target_")]
    current_features = sample_features_df[feature_cols].tail(1)

    # Act
    predictions = forecast_engine.predict(current_features)

    # Assert
    assert "baseline_change_7d" in predictions
    assert "baseline_change_30d" in predictions
    assert "model_rmse_7d" in predictions
    assert isinstance(predictions["baseline_change_7d"], float)
    assert isinstance(predictions["baseline_change_30d"], float)
    assert predictions["model_rmse_7d"] == metrics["rmse_7d"]

def test_prediction_value_range(forecast_engine, sample_features_df):
    """Test that prediction values are within a reasonable range."""
    # Arrange
    metrics = forecast_engine.train(sample_features_df)
    report = {"rmse_7d": metrics['rmse_7d'], "rmse_30d": metrics['rmse_30d'], "feature_columns": metrics['feature_columns'], "top_features": metrics['feature_importance']}
    with open(forecast_engine.REPORT_PATH, 'w') as f:
        json.dump(report, f)
        
    feature_cols = [c for c in sample_features_df.columns if not c.startswith("target_")]
    current_features = sample_features_df[feature_cols].tail(1)

    # Act
    predictions = forecast_engine.predict(current_features)

    # Assert
    # A 7-day change of +/- 50% is highly unlikely, so this is a safe check
    assert -0.5 < predictions["baseline_change_7d"] < 0.5
    assert -0.5 < predictions["baseline_change_30d"] < 0.5
    assert not np.isnan(predictions["baseline_change_7d"])
    assert not np.isinf(predictions["baseline_change_7d"])

def test_predict_raises_error_if_models_not_found(forecast_engine):
    """Test that predict raises FileNotFoundError if models don't exist."""
    # Arrange: Create a dummy feature set, but don't train
    dummy_features = pd.DataFrame({'feature1': [1]})
    
    # Act & Assert
    with pytest.raises(FileNotFoundError):
        forecast_engine.predict(dummy_features)
