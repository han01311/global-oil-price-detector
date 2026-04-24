import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import json
import pandas as pd
from datetime import datetime, timezone, timedelta

from app.main import app
from app.schemas.forecast import ForecastResult, Briefing

# --- Fixtures ---

@pytest.fixture(scope="module")
def client():
    """A single TestClient instance for the whole module."""
    return TestClient(app)

# Mock data for the entire pipeline
@pytest.fixture
def mock_pipeline_data():
    """Provides a consistent set of mock data for all pipeline components."""
    # DataCollector mocks
    latest_prices = {
        "prices": [{"date": "2024-07-16", "wti": 100.0, "brent": 105.0}],
        "source": "eia", "last_updated": "now"
    }
    prices_df = pd.DataFrame({
        'date': pd.to_datetime([datetime(2024, 7, 16) - timedelta(days=i) for i in range(100)]),
        'wti': [100.0 - i * 0.1 for i in range(100)],
        'brent': [105.0 - i * 0.1 for i in range(100)]
    })
    macro_df = pd.DataFrame({
        'date': pd.to_datetime([datetime(2024, 7, 16) - timedelta(days=i) for i in range(100)]),
        'dollar_index': [105.0 - i * 0.05 for i in range(100)]
    })
    news_articles = [
        {"id": "news-1", "title": "OPEC+ Surprise Cut", "url": "http://a.com/1", "published_at": "2024-07-16T10:00:00Z", "data_source": "newsapi", "description": "d", "source": "s", "content_snippet": "cs"},
        {"id": "news-2", "title": "Fed Rate Hike Fears", "url": "http://a.com/2", "published_at": "2024-07-16T09:00:00Z", "data_source": "newsapi", "description": "d", "source": "s", "content_snippet": "cs"},
    ]

    # NewsClassifier mock
    classified_articles = [
        MagicMock(is_relevant=True, impact_score=3, category='supply', confidence=0.9, article=MagicMock(title="OPEC+ Surprise Cut")),
        MagicMock(is_relevant=True, impact_score=-2, category='macro', confidence=0.8, article=MagicMock(title="Fed Rate Hike Fears")),
    ]
    # Convert to dicts for the pipeline
    classified_articles_dicts = [
        {"is_relevant": True, "impact_score": 3, "category": 'supply', "confidence": 0.9, "article": {"title": "OPEC+ Surprise Cut"}},
        {"is_relevant": True, "impact_score": -2, "category": 'macro', "confidence": 0.8, "article": {"title": "Fed Rate Hike Fears"}},
    ]

    # MarketMemory mock
    similar_events = [
        {"title": "Past OPEC Cut", "similarity": 0.85, "wti_change_7d": 5.0}
    ]

    # ForecastEngine mock
    baseline_prediction = {
        "baseline_change_7d": 0.01,  # +1%
        "baseline_change_30d": 0.03, # +3%
        "model_rmse_7d": 0.02,
        "model_rmse_30d": 0.04,
    }

    # BriefingGenerator mock
    mock_briefing_text = json.dumps({
        "summary": "Forecast summary based on data.",
        "key_factors": [], "risk_scenarios": [], "similar_cases": [],
        "price_outlook": "outlook", "confidence_note": "note"
    })

    return {
        "latest_prices": latest_prices,
        "prices_df": prices_df,
        "macro_df": macro_df,
        "news_articles": news_articles,
        "classified_articles": classified_articles,
        "classified_articles_dicts": classified_articles_dicts,
        "similar_events": similar_events,
        "baseline_prediction": baseline_prediction,
        "briefing_text": mock_briefing_text
    }

# --- Integration Tests ---

@patch('app.api.forecast.DataCollector')
@patch('app.api.forecast.NewsClassifier')
@patch('app.api.forecast.MarketMemory')
@patch('app.services.forecast_engine.ForecastEngine.predict')
class TestForecastIntegration:

    async def test_full_forecast_pipeline(self, mock_predict, MockMarketMemory, MockNewsClassifier, MockDataCollector, client, mock_pipeline_data):
        """데이터 수집 → 피처 생성 → 예측 → 보정 → 최종 추정"""
        # --- 1. Setup Mocks ---
        # DataCollector
        mock_collector = MockDataCollector.return_value
        mock_collector.collect_latest_prices = AsyncMock(return_value=MagicMock(prices=[MagicMock(wti=100.0)]))
        mock_collector.collect_prices_df_for_features = AsyncMock(return_value=mock_pipeline_data['prices_df'])
        mock_collector.collect_macro_df_for_features = AsyncMock(return_value=mock_pipeline_data['macro_df'])
        mock_collector.collect_news = AsyncMock(return_value=mock_pipeline_data['news_articles'])
        
        # NewsClassifier
        mock_classifier = MockNewsClassifier.return_value
        mock_classifier.classify_batch = AsyncMock(return_value=mock_pipeline_data['classified_articles'])

        # MarketMemory
        mock_memory = MockMarketMemory.return_value
        mock_memory.is_available.return_value = True
        mock_memory.search_similar = AsyncMock(return_value=mock_pipeline_data['similar_events'])

        # ForecastEngine
        mock_predict.return_value = mock_pipeline_data['baseline_prediction']

        # --- 2. API Call ---
        response = client.get("/api/forecast/estimate")

        # --- 3. Assertions ---
        assert response.status_code == 200
        result = ForecastResult(**response.json())

        # AC2: Pipeline runs
        mock_collector.collect_latest_prices.assert_awaited_once()
        mock_classifier.classify_batch.assert_awaited_once()
        mock_memory.search_similar.assert_awaited_once()
        mock_predict.assert_called_once()

        # AC3: Result is reasonable
        assert 90 < result.current_price < 110
        assert -0.5 < result.baseline_change_7d < 0.5
        assert -0.5 < result.news_adjustment_pct < 0.5
        assert result.estimated_7d > 0
        assert result.estimated_7d_low < result.estimated_7d < result.estimated_7d_high

    async def test_forecast_with_news_adjustment(self, mock_predict, MockMarketMemory, MockNewsClassifier, MockDataCollector, client, mock_pipeline_data):
        """뉴스 보정이 적용된 추정 결과 vs 베이스라인 비교"""
        # --- 1. Setup Mocks (same as above) ---
        mock_collector = MockDataCollector.return_value
        mock_collector.collect_latest_prices = AsyncMock(return_value=MagicMock(prices=[MagicMock(wti=100.0)]))
        mock_collector.collect_prices_df_for_features = AsyncMock(return_value=mock_pipeline_data['prices_df'])
        mock_collector.collect_macro_df_for_features = AsyncMock(return_value=mock_pipeline_data['macro_df'])
        mock_collector.collect_news = AsyncMock(return_value=mock_pipeline_data['news_articles'])
        
        mock_classifier = MockNewsClassifier.return_value
        mock_classifier.classify_batch = AsyncMock(return_value=mock_pipeline_data['classified_articles'])

        mock_memory = MockMarketMemory.return_value
        mock_memory.is_available.return_value = True
        mock_memory.search_similar = AsyncMock(return_value=mock_pipeline_data['similar_events'])

        mock_predict.return_value = mock_pipeline_data['baseline_prediction']

        # --- 2. API Call ---
        response = client.get("/api/forecast/estimate")
        result = ForecastResult(**response.json())

        # --- 3. Assertions ---
        assert result.news_adjustment_pct != 0

        baseline_price_7d = result.current_price * (1 + result.baseline_change_7d)
        # Final price should be roughly baseline * (1 + news_adj)
        expected_final_price_7d = baseline_price_7d * (1 + result.news_adjustment_pct)
        
        assert result.estimated_7d == pytest.approx(expected_final_price_7d, rel=1e-3)
        assert result.estimated_7d != baseline_price_7d

    @patch('app.services.briefing_generator.BriefingGenerator.generate_briefing', new_callable=AsyncMock)
    async def test_briefing_includes_forecast(self, mock_generate_briefing, mock_predict, MockMarketMemory, MockNewsClassifier, MockDataCollector, client, mock_pipeline_data):
        """브리핑에 추정 수치가 포함되는지 확인"""
        # --- 1. Setup Mocks ---
        mock_collector = MockDataCollector.return_value
        mock_collector.collect_latest_prices = AsyncMock(return_value=MagicMock(prices=[MagicMock(wti=100.0)]))
        mock_collector.collect_prices_df_for_features = AsyncMock(return_value=mock_pipeline_data['prices_df'])
        mock_collector.collect_macro_df_for_features = AsyncMock(return_value=mock_pipeline_data['macro_df'])
        mock_collector.collect_news = AsyncMock(return_value=mock_pipeline_data['news_articles'])
        
        mock_classifier = MockNewsClassifier.return_value
        mock_classifier.classify_batch = AsyncMock(return_value=mock_pipeline_data['classified_articles'])

        mock_memory = MockMarketMemory.return_value
        mock_memory.is_available.return_value = True
        mock_memory.search_similar = AsyncMock(return_value=mock_pipeline_data['similar_events'])

        mock_predict.return_value = mock_pipeline_data['baseline_prediction']

        # Mock the briefing generator to capture its input
        mock_generate_briefing.return_value = Briefing(
            date="d", summary="s", key_factors=[], risk_scenarios=[],
            similar_cases=[], price_outlook="o", confidence_note="c", generated_at="g"
        )

        # --- 2. API Call ---
        with patch('app.api.briefing._run_forecast_pipeline', new_callable=AsyncMock) as mock_run_pipeline:
            # We need to mock the pipeline runner inside the briefing API
            # to control the inputs to the generator
            
            # First, run the pipeline once to get a valid ForecastResult object
            response = client.get("/api/forecast/estimate")
            forecast_result_obj = ForecastResult(**response.json())

            mock_run_pipeline.return_value = (
                forecast_result_obj,
                mock_pipeline_data['classified_articles_dicts'],
                mock_pipeline_data['similar_events']
            )
            
            client.get("/api/briefing/today")

        # --- 3. Assertions ---
        # AC4: Briefing explains the forecast
        mock_generate_briefing.assert_awaited_once()
        call_args = mock_generate_briefing.call_args[1]
        
        forecast_arg = call_args['forecast']
        assert isinstance(forecast_arg, ForecastResult)
        assert forecast_arg.current_price == 100.0
        assert forecast_arg.dominant_factor == 'supply'
        assert forecast_arg.news_adjustment_pct != 0

    async def test_confidence_band_reasonableness(self, mock_predict, MockMarketMemory, MockNewsClassifier, MockDataCollector, client, mock_pipeline_data):
        """신뢰구간이 비현실적으로 크거나 작지 않은지 확인"""
        # --- 1. Setup Mocks ---
        mock_collector = MockDataCollector.return_value
        mock_collector.collect_latest_prices = AsyncMock(return_value=MagicMock(prices=[MagicMock(wti=100.0)]))
        mock_collector.collect_prices_df_for_features = AsyncMock(return_value=mock_pipeline_data['prices_df'])
        mock_collector.collect_macro_df_for_features = AsyncMock(return_value=mock_pipeline_data['macro_df'])
        mock_collector.collect_news = AsyncMock(return_value=mock_pipeline_data['news_articles'])
        
        mock_classifier = MockNewsClassifier.return_value
        mock_memory = MockMarketMemory.return_value
        mock_memory.is_available.return_value = True
        mock_memory.search_similar = AsyncMock(return_value=mock_pipeline_data['similar_events'])
        mock_predict.return_value = mock_pipeline_data['baseline_prediction']

        # --- 2. Scenario 1: High variance news ---
        high_var_articles = [
            MagicMock(is_relevant=True, impact_score=5, category='supply', confidence=0.9),
            MagicMock(is_relevant=True, impact_score=-5, category='demand', confidence=0.9),
        ]
        mock_classifier.classify_batch = AsyncMock(return_value=high_var_articles)
        response_high = client.get("/api/forecast/estimate")
        result_high = ForecastResult(**response_high.json())
        band_high = result_high.estimated_7d_high - result_high.estimated_7d_low

        # --- 3. Scenario 2: Low variance news ---
        low_var_articles = [
            MagicMock(is_relevant=True, impact_score=2, category='supply', confidence=0.9),
            MagicMock(is_relevant=True, impact_score=3, category='supply', confidence=0.9),
        ]
        mock_classifier.classify_batch = AsyncMock(return_value=low_var_articles)
        response_low = client.get("/api/forecast/estimate")
        result_low = ForecastResult(**response_low.json())
        band_low = result_low.estimated_7d_high - result_low.estimated_7d_low

        # --- 4. Assertions ---
        assert band_high > band_low
        # AC3: Not unrealistic
        assert (result_high.estimated_7d_high / result_high.estimated_7d_low) < 1.5
        assert (result_low.estimated_7d_high / result_low.estimated_7d_low) < 1.5
