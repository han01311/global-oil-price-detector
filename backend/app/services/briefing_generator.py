import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Dict, Any
import httpx

from pydantic import ValidationError

from app.core.config import settings
from app.schemas.forecast import ForecastResult, Briefing

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

class BriefingGenerator:
    """AI 유가 브리핑 자동 생성기 (Ollama)"""

    CACHE_DIR = "backend/data/processed/briefings"

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
                    return Briefing(**data)
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

        prompt = self._build_briefing_prompt(
            forecast=forecast,
            articles=classified_articles,
            similar_events=similar_events,
        )

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
                    timeout=45.0
                )
                response.raise_for_status()
                response_data = json.loads(response.json()["response"])

            briefing = Briefing(
                date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                generated_at=datetime.now(timezone.utc).isoformat(),
                **response_data
            )
            
            self._save_to_cache(briefing)
            return briefing

        except httpx.HTTPError as e:
            logger.error(f"Ollama API request failed for briefing: {e}")
            raise ValueError("Failed to generate a valid briefing passing API.") from e
        except (json.JSONDecodeError, ValidationError) as e:
            resp_text = response.text if 'response' in locals() else 'N/A'
            logger.error(f"Failed to parse or validate Gemma 4 response for briefing: {e}\nResponse text: {resp_text}")
            raise ValueError("Failed to generate a valid briefing from AI model.") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred during briefing generation: {e}")
            raise

    def _build_briefing_prompt(self, forecast: ForecastResult,
                               articles: List[Dict[str, Any]],
                               similar_events: List[Dict[str, Any]]) -> str:
        """브리핑 생성을 위한 프롬프트 구성"""

        forecast_str = f"""
- Current WTI Price: ${forecast.current_price:.2f}
- 7-Day Forecast: ${forecast.estimated_7d_low:.2f} - ${forecast.estimated_7d_high:.2f} (Mid: ${forecast.estimated_7d:.2f})
- 30-Day Forecast: ${forecast.estimated_30d_low:.2f} - ${forecast.estimated_30d_high:.2f} (Mid: ${forecast.estimated_30d:.2f})
- Dominant Factor from News: {forecast.dominant_factor}
- News Adjustment: {forecast.news_adjustment_pct:+.2%}
- Model Confidence: {forecast.confidence:.1%}
"""

        articles_str = "\n".join([
            f"- Title: {a.get('article', {}).get('title', 'N/A')}\n  Category: {a.get('category', 'N/A')}, Impact Score: {a.get('impact_score', 0)}\n  Summary: {a.get('impact_summary', 'N/A')}"
            for a in articles if a.get('is_relevant')
        ][:5]) # Limit to 5 most relevant articles

        similar_events_str = "\n".join([
            f"- Event: {e.get('title', 'N/A')} ({e.get('date', 'N/A')})\n  Similarity: {e.get('similarity', 0):.1%}\n  Actual 7-day WTI Change: {e.get('wti_change_7d', 0):+.2f}%"
            for e in similar_events
        ][:3]) # Limit to 3 most similar events

        prompt = f"""
You are a senior oil market analyst at a top financial institution. Your task is to generate a daily oil price briefing for professional clients. The briefing must be objective, data-driven, and concise.

Use the provided data to construct your analysis. You MUST respond ONLY with a valid JSON object in the specified format. Do not include any other text, explanations, or markdown formatting.

[CONTEXTUAL DATA]

1. Quantitative Forecast & News Impact Analysis:
{forecast_str}

2. Key News Articles from the Last 24 Hours:
{articles_str if articles_str else "No significant news in the last 24 hours."}

3. Similar Historical Events for Context:
{similar_events_str if similar_events_str else "No similar historical events found."}

[TASK]
Based on the contextual data, generate the daily briefing.

[JSON OUTPUT FORMAT]
{{
  "summary": "string (A 3-sentence executive summary of the current market situation and outlook.)",
  "key_factors": [
    {{
      "category": "string (e.g., 'supply', 'geopolitics')",
      "description": "string (A concise analysis of this factor's impact based on the news.)",
      "impact": "string ('bullish', 'bearish', or 'neutral')",
      "score": "integer (The average impact score for this category, from -5 to 5)"
    }}
  ],
  "risk_scenarios": [
    {{
      "scenario": "string (A potential risk event, e.g., 'Unexpected OPEC+ announcement')",
      "probability": "string ('high', 'medium', or 'low')",
      "price_impact": "string (Estimated impact on price, e.g., '+$3-5/bbl')"
    }}
  ],
  "similar_cases": [
    {{
      "event": "string (Name of the historical event)",
      "date": "string (Date of the event)",
      "similarity": "float (Similarity score)",
      "actual_impact": "string (Brief description of what happened to the price then)"
    }}
  ],
  "price_outlook": "string (A concluding sentence on the likely price direction, e.g., 'Prices are expected to remain volatile with a slight upward bias.')",
  "confidence_note": "string (A note on the confidence of the forecast, mentioning any limitations or high uncertainties.)"
}}
"""
        return prompt
