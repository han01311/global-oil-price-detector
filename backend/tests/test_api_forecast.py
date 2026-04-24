import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import json
import os
import pandas as pd
from datetime import datetime, timezone, timedelta

from app.main import app
from app.schemas.forecast import ForecastResult, Briefing

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_forecast_result():
    return ForecastResult(
        current_price=100.0, estimated_7d=102.0, estimated_7d_high=105.0, estimated_7d_low=99.0,
        estimated_30d=105.0, estimated_30d_high=110.0, estimated_30d_low=100.0,
        baseline_change_7d=0.01, baseline_change_30d=0.03, news_adjustment_pct=0.01,
        confidence=0.8, dominant_factor="supply", factor_breakdown=[], generated_at="now"
    )

@pytest.fixture
def mock_briefing_result():
    return Briefing(
        date="2024-01-01", summary="summary", key_factors=[], risk_scenarios=[],
        similar_cases=[], price_outlook="outlook", confidence_note="note", generated_at="now"
    )

# --- Forecast API Tests ---

@patch('app.api.forecast._run_forecast_pipeline', new_callable=AsyncMock)
def test_get_price_estimate_success(mock_run_pipeline, client, mock_forecast_result):
    """GET /api/forecast/estimate 성공 케이스"""
    mock_run_pipeline.return_value = (mock_forecast_result, [], [])
    
    response = client.get("/api/forecast/estimate")
    
    assert response.status_code == 200
    data = response.json()
    assert data['current_price'] == 100.0
    assert data['dominant_factor'] == 'supply'
    mock_run_pipeline.assert_awaited_once()

@patch('app.api.forecast._run_forecast_pipeline', new_callable=AsyncMock)
def test_get_price_estimate_model_not_found(mock_run_pipeline, client):
    """GET /api/forecast/estimate 모델 미학습 시 503 에러"""
    mock_run_pipeline.side_effect = FileNotFoundError("Model not found")
    
    response = client.get("/api/forecast/estimate")
    
    assert response.status_code == 503
    assert "Model not trained yet" in response.json()['detail']

@patch('app.services.forecast_engine.ForecastEngine.REPORT_PATH', new_callable=lambda: "/tmp/dummy_report.json")
def test_get_model_info_success(client):
    """GET /api/forecast/model-info 성공 케이스"""
    report_data = {"trained_at": "2024-01-01", "rmse_7d": 2.5, "top_features": {"wti_price": 0.5}}
    with open("/tmp/dummy_report.json", "w") as f:
        json.dump(report_data, f)
        
    response = client.get("/api/forecast/model-info")
    
    assert response.status_code == 200
    data = response.json()
    assert data['rmse_7d'] == 2.5
    
    os.remove("/tmp/dummy_report.json")

def test_get_model_info_not_found(client):
    """GET /api/forecast/model-info 파일 없을 시 404 에러"""
    if os.path.exists("/tmp/dummy_report.json"):
        os.remove("/tmp/dummy_report.json")
        
    response = client.get("/api/forecast/model-info")
    assert response.status_code == 404

# --- Briefing API Tests ---

@patch('app.api.briefing._run_forecast_pipeline', new_callable=AsyncMock)
@patch('app.services.briefing_generator.BriefingGenerator.generate_briefing', new_callable=AsyncMock)
@patch('app.services.briefing_generator.BriefingGenerator._load_from_cache')
def test_get_today_briefing_no_cache(mock_load_cache, mock_generate, mock_run_pipeline, client, mock_forecast_result, mock_briefing_result):
    """GET /api/briefing/today 캐시 없을 때 생성"""
    mock_load_cache.return_value = None
    mock_run_pipeline.return_value = (mock_forecast_result, [], [])
    mock_generate.return_value = mock_briefing_result
    
    response = client.get("/api/briefing/today")
    
    assert response.status_code == 200
    assert response.json()['summary'] == 'summary'
    mock_load_cache.assert_called_once()
    mock_run_pipeline.assert_awaited_once()
    mock_generate.assert_awaited_once()

@patch('app.services.briefing_generator.BriefingGenerator.generate_briefing', new_callable=AsyncMock)
@patch('app.services.briefing_generator.BriefingGenerator._load_from_cache')
def test_get_today_briefing_with_cache(mock_load_cache, mock_generate, client, mock_briefing_result):
    """GET /api/briefing/today 캐시 있을 때 캐시 반환"""
    mock_load_cache.return_value = mock_briefing_result
    
    response = client.get("/api/briefing/today")
    
    assert response.status_code == 200
    assert response.json()['summary'] == 'summary'
    mock_load_cache.assert_called_once()
    mock_generate.assert_not_called()

@patch('app.api.briefing._run_forecast_pipeline', new_callable=AsyncMock)
@patch('app.services.briefing_generator.BriefingGenerator.generate_briefing', new_callable=AsyncMock)
def test_post_generate_briefing(mock_generate, mock_run_pipeline, client, mock_forecast_result, mock_briefing_result):
    """POST /api/briefing/generate 브리핑 강제 재생성"""
    mock_run_pipeline.return_value = (mock_forecast_result, [], [])
    mock_generate.return_value = mock_briefing_result
    
    response = client.post("/api/briefing/generate")
    
    assert response.status_code == 200
    assert response.json()['summary'] == 'summary'
    mock_run_pipeline.assert_awaited_once()
    mock_generate.assert_awaited_once()

@patch('app.services.briefing_generator.BriefingGenerator.CACHE_DIR', new_callable=lambda: "/tmp/briefing_cache")
def test_get_briefing_history(client, mock_briefing_result):
    """GET /api/briefing/history 과거 브리핑 조회"""
    cache_dir = "/tmp/briefing_cache"
    os.makedirs(cache_dir, exist_ok=True)
    
    today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    
    briefing1 = mock_briefing_result.model_copy(update={"date": today_str})
    briefing2 = mock_briefing_result.model_copy(update={"date": yesterday_str, "summary": "yesterday"})
    
    with open(os.path.join(cache_dir, f"{today_str}.json"), "w") as f:
        f.write(briefing1.model_dump_json())
    with open(os.path.join(cache_dir, f"{yesterday_str}.json"), "w") as f:
        f.write(briefing2.model_dump_json())
        
    response = client.get("/api/briefing/history?days=2")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]['summary'] == 'summary'
    assert data[1]['summary'] == 'yesterday'
    
    os.remove(os.path.join(cache_dir, f"{today_str}.json"))
    os.remove(os.path.join(cache_dir, f"{yesterday_str}.json"))
    os.rmdir(cache_dir)
