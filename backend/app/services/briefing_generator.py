import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import List, Dict, Any
import httpx

from pydantic import ValidationError

from app.core.config import settings
from app.schemas.forecast import ForecastResult, Briefing, CrudeOutlook

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

CRUDE_TYPES = ["dubai", "brent", "wti"]
CRUDE_LABELS = {"dubai": "두바이유", "brent": "브렌트유", "wti": "WTI"}


class BriefingGenerator:
    """AI 유가 브리핑 자동 생성기 — 유종별 독립 전망 포함"""

    CACHE_DIR = str(os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed", "briefings"))

    def __init__(self, ollama_url: str | None = None):
        self.ollama_url = (ollama_url or settings.LOCAL_LLM_URL).rstrip("/")
        self.model_name = "gemma"
        os.makedirs(self.CACHE_DIR, exist_ok=True)

    def _get_cache_path(self) -> str:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return os.path.join(self.CACHE_DIR, f"{today}.json")

    def _load_from_cache(self) -> Briefing | None:
        cache_path = self._get_cache_path()
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    briefing = Briefing(**data)
                    if self._is_korean_briefing(briefing):
                        return briefing
                    logger.warning("Ignoring non-Korean briefing cache: %s", cache_path)
                    return None
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error(f"Failed to load briefing from cache: {e}")
                return None
        return None

    def _save_to_cache(self, briefing: Briefing):
        cache_path = self._get_cache_path()
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(briefing.model_dump(), f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"Failed to save briefing to cache: {e}")

    async def generate_briefing(self, forecast: ForecastResult,
                                 classified_articles: List[Dict[str, Any]],
                                 similar_events: List[Dict[str, Any]]) -> Briefing:
        """일일 유가 브리핑 생성. 캐시를 먼저 확인."""
        cached_briefing = self._load_from_cache()
        if cached_briefing:
            logger.info("Loaded briefing from cache.")
            return cached_briefing

        if not classified_articles and not similar_events:
            briefing = self._get_fallback_briefing(forecast)
            self._save_to_cache(briefing)
            return briefing

        prompt = self._build_briefing_prompt(
            forecast=forecast,
            articles=classified_articles,
            similar_events=similar_events,
        )

        max_retries = 1
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.ollama_url}/api/generate",
                        json={
                            "model": self.model_name,
                            "prompt": prompt,
                            "format": "json",
                            "stream": False
                        },
                        timeout=30.0
                    )
                    response.raise_for_status()
                    
                    resp_text = response.json().get("response", "")
                    try:
                        response_data = json.loads(resp_text)
                    except json.JSONDecodeError:
                        logger.warning("Failed direct JSON parsing, attempting Regex extraction...")
                        match = re.search(r'\{.*\}', resp_text, re.DOTALL)
                        if match:
                            response_data = json.loads(match.group(0))
                        else:
                            raise ValueError("No JSON object could be extracted from response.")

                # Parse crude_outlooks
                raw_outlooks = response_data.pop("crude_outlooks", [])
                crude_outlooks = []
                for outlook in raw_outlooks:
                    try:
                        crude_outlooks.append(CrudeOutlook(**outlook))
                    except (ValidationError, TypeError) as e:
                        logger.warning(f"Failed to parse crude outlook: {e}")

                briefing = Briefing(
                    date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    generated_at=datetime.now(timezone.utc).isoformat(),
                    crude_outlooks=crude_outlooks,
                    **response_data
                )
                if not self._is_korean_briefing(briefing):
                    logger.warning("LLM returned a non-Korean briefing. Returning fallback briefing.")
                    briefing = self._get_fallback_briefing(forecast)
                
                self._save_to_cache(briefing)
                return briefing

            except (httpx.HTTPError, ValueError, json.JSONDecodeError, ValidationError) as e:
                logger.error(f"Attempt {attempt + 1}: Failed to generate briefing. Error: {e}")
                if attempt == max_retries:
                    logger.warning("All attempts failed. Returning fallback briefing.")
                    return self._get_fallback_briefing(forecast)

    def _get_fallback_briefing(self, forecast: ForecastResult) -> Briefing:
        from app.schemas.forecast import BriefingKeyFactor, RiskScenario, SimilarCase, CrudeOutlook

        # Generate fallback crude outlooks from forecasts_by_crude
        crude_outlooks = []
        for crude, cf in forecast.forecasts_by_crude.items():
            direction = "bullish" if cf.news_adjustment_pct > 0 else ("bearish" if cf.news_adjustment_pct < 0 else "neutral")
            crude_outlooks.append(CrudeOutlook(
                crude_type=crude,
                direction=direction,
                summary=f"{CRUDE_LABELS.get(crude, crude)} 기본 추정 모델 기반 전망입니다.",
                key_driver="정량 모델 기반 (정성 분석 지연)"
            ))

        return Briefing(
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            generated_at=datetime.now(timezone.utc).isoformat(),
            summary="일시적인 AI 분석 지연으로 인해 요약 브리핑을 불러오지 못했습니다.",
            key_factors=[BriefingKeyFactor(category="unknown", description="현재 구체적인 요인을 분석할 수 없습니다.", impact="neutral", score=0)],
            risk_scenarios=[RiskScenario(scenario="수집/분석 지연", probability="low", price_impact="N/A")],
            similar_cases=[],
            crude_outlooks=crude_outlooks,
            price_outlook="기본 추정 모델에 따라 당분간 밴드 내 변동성을 보일 것으로 예상됩니다.",
            confidence_note="AI 모델 응답 지연으로 정성적 보정 신뢰도가 임시로 낮아졌습니다."
        )

    def _has_hangul(self, value: str | None) -> bool:
        return bool(value and re.search(r"[가-힣]", value))

    def _is_korean_briefing(self, briefing: Briefing) -> bool:
        text_values = [
            briefing.summary,
            briefing.price_outlook,
            briefing.confidence_note,
        ]
        text_values.extend(f.description for f in briefing.key_factors)
        text_values.extend(s.scenario for s in briefing.risk_scenarios)
        text_values.extend(o.summary for o in briefing.crude_outlooks)
        required = [value for value in text_values if value]
        return bool(required) and sum(1 for value in required if self._has_hangul(value)) >= max(1, len(required) // 2)

    def _build_briefing_prompt(self, forecast: ForecastResult,
                               articles: List[Dict[str, Any]],
                               similar_events: List[Dict[str, Any]]) -> str:
        """브리핑 생성을 위한 프롬프트 구성 — 유종별 독립 전망 포함"""

        # Build per-crude forecast summary
        crude_forecast_lines = []
        for crude in CRUDE_TYPES:
            cf = forecast.forecasts_by_crude.get(crude)
            if cf:
                label = CRUDE_LABELS.get(crude, crude.upper())
                crude_forecast_lines.append(f"""
  [{label}]
  - Current Price: ${cf.current_price:.2f}
  - 7-Day Forecast: ${cf.estimated_7d_low:.2f} - ${cf.estimated_7d_high:.2f} (Mid: ${cf.estimated_7d:.2f})
  - 30-Day Forecast: ${cf.estimated_30d_low:.2f} - ${cf.estimated_30d_high:.2f} (Mid: ${cf.estimated_30d:.2f})
  - News Adjustment: {cf.news_adjustment_pct:+.2%}
  - Dominant Factor: {cf.dominant_factor or 'N/A'}
  - Confidence: {cf.confidence:.1%}""")

        crude_forecasts_str = "\n".join(crude_forecast_lines) if crude_forecast_lines else "No per-crude forecasts available."

        # Legacy WTI summary for backward compat
        forecast_str = f"""
- Overall Current Price (WTI): ${forecast.current_price:.2f}
- 7-Day Forecast: ${forecast.estimated_7d_low:.2f} - ${forecast.estimated_7d_high:.2f} (Mid: ${forecast.estimated_7d:.2f})
- 30-Day Forecast: ${forecast.estimated_30d_low:.2f} - ${forecast.estimated_30d_high:.2f} (Mid: ${forecast.estimated_30d:.2f})
- Model Confidence: {forecast.confidence:.1%}
"""

        articles_str = "\n".join([
            f"- Title: {a.get('article', {}).get('title', 'N/A')}\n  Category: {a.get('category', 'N/A')}, Impact Score: {a.get('impact_score', 0)}\n  Summary: {a.get('impact_summary', 'N/A')}\n  Dubai Impact: {a.get('impact_by_crude', {}).get('dubai', {}).get('score', 'N/A') if isinstance(a.get('impact_by_crude', {}).get('dubai'), dict) else 'N/A'}, Brent: {a.get('impact_by_crude', {}).get('brent', {}).get('score', 'N/A') if isinstance(a.get('impact_by_crude', {}).get('brent'), dict) else 'N/A'}, WTI: {a.get('impact_by_crude', {}).get('wti', {}).get('score', 'N/A') if isinstance(a.get('impact_by_crude', {}).get('wti'), dict) else 'N/A'}"
            for a in articles if a.get('is_relevant')
        ][:5])

        similar_events_str = "\n".join([
            f"- Event: {e.get('title', 'N/A')} ({e.get('date', 'N/A')})\n  Similarity: {e.get('similarity', 0):.1%}\n  WTI 7d: {e.get('wti_change_7d', 'N/A'):+.2f}%"
            for e in similar_events
        ][:3])

        prompt = f"""
You are a senior oil market analyst at a top financial institution. Your task is to generate a daily oil price briefing for professional clients. The briefing must be objective, data-driven, and concise.

IMPORTANT: All text values in the JSON output MUST be written in Korean (한국어). Do NOT translate the JSON keys.

CRITICAL: You must provide INDEPENDENT outlooks for each crude type (Dubai, Brent, WTI). Each crude type has different geopolitical sensitivities, so their outlooks may differ significantly.

Use the provided data to construct your analysis. You MUST respond ONLY with a valid JSON object in the specified format.

[CONTEXTUAL DATA]

1. Overall Quantitative Forecast:
{forecast_str}

2. Per-Crude Independent Forecasts:
{crude_forecasts_str}

3. Key News Articles (with per-crude impact):
{articles_str if articles_str else "No significant news in the last 24 hours."}

4. Similar Historical Events:
{similar_events_str if similar_events_str else "No similar historical events found."}

[TASK]
Based on the contextual data, generate the daily briefing with independent per-crude outlooks.

[JSON OUTPUT FORMAT]
{{
  "summary": "string (반드시 한국어로 작성. 3개 유종을 모두 아우르는 3문장 이내의 핵심 요약)",
  "key_factors": [
    {{
      "category": "string (예: '공급', '지정학', '수요' 등 한국어로 작성)",
      "description": "string (반드시 한국어로 작성. 이 요인이 유가에 미치는 영향에 대한 상세 분석)",
      "impact": "string ('bullish', 'bearish', 또는 'neutral' 중 하나로 영문 유지)",
      "score": "integer (-5 to 5)"
    }}
  ],
  "risk_scenarios": [
    {{
      "scenario": "string (반드시 한국어로 작성. 발생 가능한 시장 리스크 시나리오)",
      "probability": "string ('high', 'medium', 또는 'low' 중 하나로 영문 유지)",
      "price_impact": "string (예: '+$3-5/bbl')"
    }}
  ],
  "similar_cases": [
    {{
      "event": "string (과거 유사 사례 이벤트명, 한국어로 작성)",
      "date": "string",
      "similarity": "float",
      "actual_impact": "string (실제 가격에 미친 영향, 한국어로 작성)"
    }}
  ],
  "crude_outlooks": [
    {{
      "crude_type": "string ('dubai', 'brent', 또는 'wti')",
      "direction": "string ('bullish', 'bearish', 또는 'neutral')",
      "summary": "string (반드시 한국어로 작성. 해당 유종에 특화된 2문장 이내의 전망)",
      "key_driver": "string (반드시 한국어로 작성. 해당 유종의 가격 변동을 이끄는 핵심 동인)"
    }}
  ],
  "price_outlook": "string (반드시 한국어로 작성. 종합적인 유가 방향성 결론)",
  "confidence_note": "string (반드시 한국어로 작성. 예측 신뢰도 및 한계점에 대한 코멘트)"
}}
"""
        return prompt
