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
            "impact_summary": "OPEC+ 감산은 공급 부족 우려를 키웁니다.",
            "impact_by_crude": {
                "dubai": {"score": 3, "direction": "bullish"},
                "brent": {"score": 2, "direction": "bullish"},
                "wti": {"score": 1, "direction": "neutral"},
            }
        },
        {
            "article": {"title": "Fed Hints at Rate Hike"},
            "is_relevant": True,
            "category": "macro",
            "impact_score": -2,
            "impact_summary": "금리 인상 가능성은 달러 강세를 유발합니다.",
            "impact_by_crude": {
                "dubai": {"score": -1, "direction": "bearish"},
                "brent": {"score": -1, "direction": "bearish"},
                "wti": {"score": -2, "direction": "bearish"},
            }
        }
    ]

@pytest.fixture
def mock_price_data():
    return {
        "dubai": {"today": 71.5, "yesterday": 70.0},
        "brent": {"today": 75.0, "yesterday": 75.5},
        "wti": {"today": 68.0, "yesterday": 68.0},
    }

@pytest.fixture
def briefing_generator(tmp_path):
    generator = BriefingGenerator(ollama_url="http://test_ollama:11434")
    generator.CACHE_DIR = str(tmp_path)
    return generator

@pytest.fixture
def mock_httpx_response():
    mock_response_text = {
        "summary": "국제 유가는 OPEC+ 감산 결정으로 상승 압력을 받고 있음.",
        "key_factors": [{"category": "공급", "description": "OPEC+ 감산은 공급 부족 우려를 키움.", "impact": "bullish", "score": 4}],
        "risk_scenarios": [{"scenario": "중동 지정학적 긴장 고조", "probability": "medium", "price_impact": "+$5"}],
        "price_outlook": "단기적으로 유가는 혼조세를 보일 것으로 예상됨.",
        "confidence_note": "뉴스 기반 분석 신뢰도 높음."
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"response": json.dumps(mock_response_text)}
    return mock_resp


def test_compute_crude_assessments(briefing_generator, mock_price_data, mock_classified_articles):
    """유종별 당일 시세 평가가 결정론적으로 정확히 계산되는지 확인"""
    assessments = briefing_generator._compute_crude_assessments(mock_price_data, mock_classified_articles)
    
    assert len(assessments) == 3
    
    # Dubai: (71.5 - 70.0) / 70.0 * 100 = 2.14% → bullish
    dubai = next(a for a in assessments if a.crude_type == "dubai")
    assert dubai.direction == "bullish"
    assert dubai.change_pct == pytest.approx(2.14, abs=0.01)
    assert dubai.key_driver  # 키워드가 채워져 있어야 함
    
    # Brent: (75.0 - 75.5) / 75.5 * 100 = -0.66% → bearish
    brent = next(a for a in assessments if a.crude_type == "brent")
    assert brent.direction == "bearish"
    assert brent.change_pct == pytest.approx(-0.66, abs=0.01)
    
    # WTI: (68.0 - 68.0) / 68.0 * 100 = 0.0% → neutral
    wti = next(a for a in assessments if a.crude_type == "wti")
    assert wti.direction == "neutral"
    assert wti.change_pct == pytest.approx(0.0, abs=0.01)


def test_extract_crude_drivers(briefing_generator, mock_classified_articles):
    """뉴스 기사에서 유종별 핵심 요인 키워드를 정확히 추출하는지 확인"""
    drivers = briefing_generator._extract_crude_drivers(mock_classified_articles)
    
    assert "dubai" in drivers
    assert "brent" in drivers
    assert "wti" in drivers
    # Dubai에서 가장 높은 영향도는 supply(score=3)
    assert "공급" in drivers["dubai"]
    # WTI에서 가장 높은 영향도는 macro(score=2)
    assert "거시" in drivers["wti"]


def test_build_briefing_prompt(briefing_generator, mock_forecast_result, mock_classified_articles):
    prompt = briefing_generator._build_briefing_prompt(
        forecast=mock_forecast_result,
        articles=mock_classified_articles,
    )

    assert "OPEC+ Surprise Cut" in prompt
    assert "Fed Hints at Rate Hike" in prompt
    assert "JSON OUTPUT FORMAT" in prompt
    # crude_outlooks 관련 내용이 없어야 함
    assert "crude_outlooks" not in prompt


@pytest.mark.asyncio
@patch('httpx.AsyncClient.post')
async def test_generate_briefing_success(mock_post, briefing_generator, mock_forecast_result, mock_classified_articles, mock_price_data, mock_httpx_response):
    mock_post.return_value = mock_httpx_response

    result = await briefing_generator.generate_briefing(
        forecast=mock_forecast_result,
        classified_articles=mock_classified_articles,
        price_data=mock_price_data,
    )

    mock_post.assert_awaited_once()
    assert isinstance(result, Briefing)
    assert "OPEC+" in result.summary or "감산" in result.summary
    assert len(result.key_factors) == 1
    assert result.key_factors[0].category == "공급"
    # crude_assessments는 결정론적으로 채워져야 함
    assert len(result.crude_assessments) == 3
    assert result.has_news is True


@pytest.mark.asyncio
@patch('httpx.AsyncClient.post')
async def test_caching_mechanism(mock_post, briefing_generator, mock_forecast_result, mock_classified_articles, mock_price_data, mock_httpx_response):
    mock_post.return_value = mock_httpx_response

    result1 = await briefing_generator.generate_briefing(
        forecast=mock_forecast_result,
        classified_articles=mock_classified_articles,
        price_data=mock_price_data,
    )
    mock_post.assert_awaited_once()
    
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cache_file = os.path.join(briefing_generator.CACHE_DIR, f"{today_str}.json")
    assert os.path.exists(cache_file)

    result2 = await briefing_generator.generate_briefing(
        forecast=mock_forecast_result,
        classified_articles=mock_classified_articles,
        price_data=mock_price_data,
    )
    assert mock_post.call_count == 1
    
    assert result1.model_dump() == result2.model_dump()


@pytest.mark.asyncio
async def test_generate_briefing_no_articles(briefing_generator, mock_forecast_result, mock_price_data):
    """뉴스 기사 없으면 has_news=False로 최소 브리핑 반환"""
    result = await briefing_generator.generate_briefing(
        forecast=mock_forecast_result,
        classified_articles=[],
        price_data=mock_price_data,
    )

    assert result.has_news is False
    assert "수집되지 않" in result.summary
    assert isinstance(result, Briefing)
    # 가격 데이터는 있으므로 crude_assessments는 채워져야 함
    assert len(result.crude_assessments) == 3


def test_model_name_is_gemma4_e4b(briefing_generator):
    """모델명이 gemma4:e4b인지 확인"""
    assert briefing_generator.model_name == "gemma4:e4b"
