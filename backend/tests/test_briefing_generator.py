import pytest
import json
import os
import asyncio
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from app.services.briefing_generator import BriefingGenerator
from app.schemas.forecast import ForecastResult, Briefing

@pytest.fixture
def mock_forecast_result():
    return ForecastResult(
        current_price=100.0,
        estimated_7d=102.5,
        estimated_7d_high=105.0,
        estimated_7d_low=100.0,
        estimated_30d=105.0,
        estimated_30d_high=110.0,
        estimated_30d_low=100.0,
        baseline_change_7d=0.01,
        baseline_change_30d=0.03,
        news_adjustment_pct=0.015,
        confidence=0.75,
        dominant_factor="supply",
        factor_breakdown=[],
        generated_at="2024-01-01T00:00:00Z"
    )

@pytest.fixture
def mock_classified_articles():
    return [
        {
            "article": {"title": "OPEC+ Surprise Cut"},
            "is_relevant": True,
            "category": "supply",
            "impact_score": 4,
            "impact_summary": "OPEC+ 감산은 공급 부족 우려를 키웁니다."
        },
        {
            "article": {"title": "Fed Hints at Rate Hike"},
            "is_relevant": True,
            "category": "macro",
            "impact_score": -2,
            "impact_summary": "금리 인상 가능성은 달러 강세를 유발합니다."
        }
    ]

@pytest.fixture
def mock_similar_events():
    return [
        {
            "title": "2022 Ukraine Invasion",
            "date": "2022-02-24",
            "similarity": 0.85,
            "wti_change_7d": 15.5
        }
    ]

@pytest.fixture
def briefing_generator(tmp_path):
    generator = BriefingGenerator(ollama_url="http://test_ollama:11434")
    generator.CACHE_DIR = str(tmp_path)
    return generator

@pytest.fixture
def mock_httpx_response():
    mock_response_text = {
        "summary": "A three-sentence summary.",
        "key_factors": [{"category": "supply", "description": "desc", "impact": "bullish", "score": 4}],
        "risk_scenarios": [{"scenario": "risk", "probability": "medium", "price_impact": "+$5"}],
        "similar_cases": [{"event": "case", "date": "2022-01-01", "similarity": 0.8, "actual_impact": "Price went up."}],
        "price_outlook": "Outlook is positive.",
        "confidence_note": "Confidence is high."
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"response": json.dumps(mock_response_text)}
    return mock_resp

def test_build_briefing_prompt(briefing_generator, mock_forecast_result, mock_classified_articles, mock_similar_events):
    prompt = briefing_generator._build_briefing_prompt(
        forecast=mock_forecast_result,
        articles=mock_classified_articles,
        similar_events=mock_similar_events
    )

    assert "$100.00" in prompt
    assert "Dominant Factor from News: supply" in prompt
    assert "+1.50%" in prompt
    assert "OPEC+ Surprise Cut" in prompt
    assert "Fed Hints at Rate Hike" in prompt
    assert "2022 Ukraine Invasion" in prompt
    assert "+15.50%" in prompt
    assert "JSON OUTPUT FORMAT" in prompt

@pytest.mark.asyncio
@patch('httpx.AsyncClient.post')
async def test_generate_briefing_success(mock_post, briefing_generator, mock_forecast_result, mock_classified_articles, mock_similar_events, mock_httpx_response):
    mock_post.return_value = mock_httpx_response

    result = await briefing_generator.generate_briefing(
        forecast=mock_forecast_result,
        classified_articles=mock_classified_articles,
        similar_events=mock_similar_events
    )

    mock_post.assert_awaited_once()
    assert isinstance(result, Briefing)
    assert result.summary == "A three-sentence summary."
    assert len(result.key_factors) == 1
    assert result.key_factors[0].category == "supply"
    assert result.price_outlook == "Outlook is positive."

@pytest.mark.asyncio
@patch('httpx.AsyncClient.post')
async def test_caching_mechanism(mock_post, briefing_generator, mock_forecast_result, mock_classified_articles, mock_similar_events, mock_httpx_response):
    mock_post.return_value = mock_httpx_response

    result1 = await briefing_generator.generate_briefing(
        forecast=mock_forecast_result,
        classified_articles=mock_classified_articles,
        similar_events=mock_similar_events
    )
    mock_post.assert_awaited_once()
    
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cache_file = os.path.join(briefing_generator.CACHE_DIR, f"{today_str}.json")
    assert os.path.exists(cache_file)

    result2 = await briefing_generator.generate_briefing(
        forecast=mock_forecast_result,
        classified_articles=mock_classified_articles,
        similar_events=mock_similar_events
    )
    assert mock_post.call_count == 1
    
    assert result1.model_dump() == result2.model_dump()

@pytest.mark.asyncio
@patch('httpx.AsyncClient.post')
async def test_generate_briefing_invalid_response(mock_post, briefing_generator, mock_forecast_result, mock_classified_articles, mock_similar_events):
    invalid_json_resp = MagicMock()
    invalid_json_resp.raise_for_status = MagicMock()
    invalid_json_resp.json.return_value = {"response": '{"summary": "incomplete...'}
    mock_post.return_value = invalid_json_resp

    result = await briefing_generator.generate_briefing(
        forecast=mock_forecast_result,
        classified_articles=mock_classified_articles,
        similar_events=mock_similar_events
    )

    assert result.summary == "일시적인 AI 분석 지연으로 인해 요약 브리핑을 불러오지 못했습니다."
