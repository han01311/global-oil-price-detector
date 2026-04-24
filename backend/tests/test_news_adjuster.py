import pytest
import pandas as pd
from unittest.mock import MagicMock, AsyncMock

from app.services.forecast_engine import NewsAdjuster, HybridForecaster, ForecastEngine
from app.schemas.forecast import ForecastResult

@pytest.fixture
def adjuster():
    return NewsAdjuster()

def test_sentiment_to_pct(adjuster):
    """감성->변동률 변환 정확도 테스트"""
    assert adjuster._sentiment_to_pct(0) == 0.0
    assert pytest.approx(adjuster._sentiment_to_pct(5)) == 0.05
    assert pytest.approx(adjuster._sentiment_to_pct(-5)) == -0.05
    assert pytest.approx(adjuster._sentiment_to_pct(3)) == 0.02323, "3 should map to ~2.3%"
    assert pytest.approx(adjuster._sentiment_to_pct(-1)) == -0.00447, "-1 should map to ~-0.45%"

def test_calculate_similar_adjustment(adjuster):
    """유사 사례 가중 평균 계산 테스트"""
    events = [
        {"similarity": 0.9, "wti_change_7d": 5.0},
        {"similarity": 0.8, "wti_change_7d": -2.0},
        {"similarity": 0.7, "wti_change_7d": None}, # ignored
        {"similarity": 0.4, "wti_change_7d": 10.0}, # ignored (similarity < 0.5)
    ]
    # (0.9 * 0.05 + 0.8 * -0.02) / (0.9 + 0.8) = 0.029 / 1.7 = 0.01705
    expected = 0.01705
    assert pytest.approx(adjuster._calculate_similar_adjustment(events)) == expected

def test_calculate_uncertainty(adjuster):
    """불확실성 계산 테스트"""
    articles_high_var = [{"is_relevant": True, "impact_score": 5}, {"is_relevant": True, "impact_score": -5}]
    articles_low_var = [{"is_relevant": True, "impact_score": 2}, {"is_relevant": True, "impact_score": 3}]
    articles_single = [{"is_relevant": True, "impact_score": 5}]

    uncertainty_high = adjuster._calculate_uncertainty(articles_high_var)
    uncertainty_low = adjuster._calculate_uncertainty(articles_low_var)
    uncertainty_single = adjuster._calculate_uncertainty(articles_single)

    assert uncertainty_high > uncertainty_low
    assert uncertainty_single == 0.005
    assert uncertainty_high > 0.015

@pytest.mark.asyncio
async def test_calculate_adjustment(adjuster):
    """최종 보정값 산출 정합성 테스트"""
    articles = [
        {"is_relevant": True, "impact_score": 3, "confidence": 0.9, "category": "supply"},
        {"is_relevant": True, "impact_score": -1, "confidence": 0.8, "category": "demand"},
        {"is_relevant": False, "impact_score": 5, "confidence": 0.9, "category": "geopolitics"},
    ]
    similar_events = [{"similarity": 0.9, "wti_change_7d": 2.0}]

    result = await adjuster.calculate_adjustment(articles, similar_events)

    # sentiment: (3*0.9 + -1*0.8) / 2 = 1.9 / 2 = 0.95
    assert pytest.approx(result["sentiment_component"]) == 0.95
    # similar: (0.9 * 0.02) / 0.9 = 0.02
    assert pytest.approx(result["similar_component"]) == 0.02
    
    # sentiment_pct: _sentiment_to_pct(0.95) -> approx 0.00414
    sentiment_pct = adjuster._sentiment_to_pct(0.95)
    # adjustment: 0.4 * sentiment_pct + 0.6 * 0.02 = 0.001656 + 0.012 = 0.013656
    assert pytest.approx(result["news_adjustment_pct"]) == 0.013656
    assert result["article_count"] == 2
    assert result["dominant_category"] == "supply"

@pytest.fixture
def hybrid_forecaster():
    mock_engine = MagicMock(spec=ForecastEngine)
    mock_engine.predict.return_value = {
        "baseline_change_7d": 0.01,
        "baseline_change_30d": 0.02,
        "model_rmse_7d": 0.025,
        "model_rmse_30d": 0.04,
    }
    adjuster_instance = NewsAdjuster()
    return HybridForecaster(engine=mock_engine, adjuster=adjuster_instance)

@pytest.mark.asyncio
async def test_hybrid_forecast(hybrid_forecaster):
    """최종 밴드 산출 정합성 테스트"""
    current_price = 100.0
    articles = [
        {"is_relevant": True, "impact_score": 2, "confidence": 0.9, "category": "supply"}
    ]
    events = [
        {"similarity": 0.8, "wti_change_7d": 1.0}
    ]

    result = await hybrid_forecaster.forecast(current_price, pd.DataFrame(), articles, events)

    assert isinstance(result, ForecastResult)
    
    # AC 1 & 2: Check adjustment and final price
    # sentiment_score = (2*0.9)/1 = 1.8. sentiment_pct = _sentiment_to_pct(1.8) = 0.0107
    # similar_adj = (0.8 * 0.01) / 0.8 = 0.01
    # news_adj = 0.4 * 0.0107 + 0.6 * 0.01 = 0.00428 + 0.006 = 0.01028
    assert pytest.approx(result.news_adjustment_pct) == 0.01028
    # final_change = (1 + 0.01) * (1 + 0.01028) - 1 = 1.01 * 1.01028 - 1 = 0.02038
    expected_price = 100.0 * (1 + 0.02038) # 102.038
    assert pytest.approx(result.estimated_7d) == expected_price

    # AC 3: Check confidence band
    # uncertainty = 0.005 (base for 1 article)
    # band_width = 0.025 (rmse) + 0.005 = 0.03
    band_width = 0.03
    expected_high = expected_price * (1 + band_width)
    expected_low = expected_price * (1 - band_width)
    assert pytest.approx(result.estimated_7d_high) == expected_high
    assert pytest.approx(result.estimated_7d_low) == expected_low

    # AC 4: Check schema fields
    assert result.dominant_factor == "supply"
    assert len(result.factor_breakdown) == 1
