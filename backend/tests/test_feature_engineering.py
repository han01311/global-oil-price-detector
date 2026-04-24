import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from app.services.feature_engineering import FeatureEngineer

@pytest.fixture
def sample_data():
    """Generates sample price and macro data for testing."""
    # Need enough data for a 50-day MA and a 30-day target lookahead
    # Total rows = 50 (for MA) + 30 (for target) + some buffer = 100
    dates = [datetime(2023, 1, 1) + timedelta(days=i) for i in range(100)]
    
    prices_df = pd.DataFrame({
        'date': [d.strftime('%Y-%m-%d') for d in dates],
        'wti': np.linspace(70, 85, 100) + np.random.randn(100) * 0.5,
        'brent': np.linspace(75, 90, 100) + np.random.randn(100) * 0.5,
    })

    macro_df = pd.DataFrame({
        'date': [d.strftime('%Y-%m-%d') for d in dates],
        'fed_rate': np.nan,
        'dollar_index': np.linspace(100, 105, 100),
        'yield_spread': np.linspace(0.5, 0.2, 100),
    })
    # Simulate monthly data for fed_rate
    macro_df.loc[macro_df.index % 30 == 0, 'fed_rate'] = np.linspace(3.0, 3.5, len(macro_df[macro_df.index % 30 == 0]))

    return prices_df, macro_df

@pytest.fixture
def feature_engineer():
    """Returns an instance of FeatureEngineer."""
    return FeatureEngineer()

def test_build_features_creates_sufficient_features(feature_engineer, sample_data):
    """AC 1: 원시 데이터로부터 최소 20개 이상의 피처가 생성된다"""
    prices_df, macro_df = sample_data
    features = feature_engineer.build_features(prices_df, macro_df)
    
    assert len(features.columns) >= 20

def test_build_features_handles_nans(feature_engineer, sample_data):
    """AC 2: NaN이 적절히 처리된다 (dropna 또는 ffill)"""
    prices_df, macro_df = sample_data
    features = feature_engineer.build_features(prices_df, macro_df)
    
    assert not features.isnull().values.any()
    assert features['fed_rate'].iloc[0] is not None

def test_build_features_no_future_leakage(feature_engineer, sample_data):
    """AC 3: 미래 정보 누출이 없다 (타겟 변수가 미래 데이터를 shift)"""
    prices_df, macro_df = sample_data
    
    features = feature_engineer.build_features(prices_df.copy(), macro_df.copy())
    
    sample_date = features.index[10]
    
    wti_t0 = prices_df.set_index('date').loc[sample_date.strftime('%Y-%m-%d'), 'wti']
    
    sample_date_t7 = sample_date + timedelta(days=7)
    wti_t7 = prices_df.set_index('date').loc[sample_date_t7.strftime('%Y-%m-%d'), 'wti']
    
    expected_target_7d = (wti_t7 / wti_t0) - 1
    actual_target_7d = features.loc[sample_date, 'target_7d']
    
    assert np.isclose(actual_target_7d, expected_target_7d)

def test_split_train_test_is_sequential(feature_engineer, sample_data):
    """AC 4: train/test 분할이 시계열 순서를 유지한다"""
    prices_df, macro_df = sample_data
    features = feature_engineer.build_features(prices_df, macro_df)
    
    train_df, test_df = feature_engineer.split_train_test(features, test_ratio=0.2)
    
    assert train_df.index[-1] < test_df.index[0]
    assert train_df.index.is_monotonic_increasing
    assert test_df.index.is_monotonic_increasing
    
    expected_test_size = int(len(features) * 0.2)
    assert abs(len(test_df) - expected_test_size) <= 1
