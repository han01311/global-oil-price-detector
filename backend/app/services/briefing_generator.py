from __future__ import annotations
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import List, Dict, Any
import httpx

from pydantic import ValidationError

from app.core.config import settings
from app.schemas.forecast import ForecastResult, Briefing, CrudeDailyAssessment, AnalyzedArticle

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

CRUDE_TYPES = ["dubai", "wti", "brent"]
CRUDE_LABELS = {"dubai": "Dubai", "brent": "Brent", "wti": "WTI"}


class BriefingGenerator:
    """AI 유가 브리핑 자동 생성기 — 뉴스 분류 완료 후 실행, 일자별 저장"""

    CACHE_DIR = str(os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed", "briefings"))

    def __init__(self, ollama_url: str | None = None):
        self.ollama_url = (ollama_url or settings.LOCAL_LLM_URL).rstrip("/")
        self.model_name = "gemma4:e4b"
        os.makedirs(self.CACHE_DIR, exist_ok=True)

    def _get_cache_path(self, target_date: str | None = None) -> str:
        date_str = target_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return os.path.join(self.CACHE_DIR, f"{date_str}.json")

    def _load_from_cache(self, target_date: str | None = None) -> Briefing | None:
        cache_path = self._get_cache_path(target_date)
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
        cache_path = self._get_cache_path(briefing.date)
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(briefing.model_dump(), f, ensure_ascii=False, indent=2)
            logger.info(f"Briefing saved to cache: {cache_path}")
        except IOError as e:
            logger.error(f"Failed to save briefing to cache: {e}")

    # ──────────────────────────────────────────────
    # 유종별 당일 시세 평가 — 결정론적 계산
    # ──────────────────────────────────────────────
    def _compute_crude_assessments(
        self,
        price_data: Dict[str, Dict[str, float]],
        classified_articles: List[Dict[str, Any]]
    ) -> List[CrudeDailyAssessment]:
        """
        DB에서 조회한 유종별 최근/직전 거래일 가격과 분류된 뉴스로부터
        결정론적으로 시세 변동 평가를 산출한다.
        
        price_data 형식: {"dubai": {"today": 70.5, "yesterday": 69.8}, ...}
        """
        assessments = []
        
        # 뉴스 기사에서 유종별 dominant factor 추출
        crude_drivers = self._extract_crude_drivers(classified_articles)
        
        for crude in CRUDE_TYPES:
            # 뉴스 기사들의 Impact Score를 합산하여 AI 센티먼트 방향성 평가
            total_score = 0
            for article in classified_articles:
                crude_impact = article.get("impact_by_crude", {}).get(crude, {})
                if isinstance(crude_impact, dict):
                    score = crude_impact.get("score", 0)
                    total_score += score
            
            # 방향성 결정: 0 이상이면 상승 압력, 0 미만이면 하락 압력, 0이면 관망세
            if total_score > 0:
                direction = "bullish"
            elif total_score < 0:
                direction = "bearish"
            else:
                direction = "neutral"
            
            # 프론트엔드 타입 호환성을 위해 change_pct는 total_score로 전달 (UI에서는 사용 안함)
            change_pct = float(total_score)
            
            key_driver = crude_drivers.get(crude, "데이터 부족")
            
            assessments.append(CrudeDailyAssessment(
                crude_type=crude,
                direction=direction,
                change_pct=change_pct,
                key_driver=key_driver,
            ))
        
        return assessments

    def _extract_crude_drivers(self, articles: List[Dict[str, Any]]) -> Dict[str, str]:
        """분류된 뉴스 기사에서 유종별 가장 영향력 높은 요인의 기사 요약을 추출"""
        crude_drivers: Dict[str, str] = {}
        
        for crude in CRUDE_TYPES:
            best_score = 0
            best_summary = ""
            
            for article in articles:
                if not article.get("is_relevant"):
                    continue
                impact_by_crude = article.get("impact_by_crude", {})
                crude_impact = impact_by_crude.get(crude, {})
                if isinstance(crude_impact, dict):
                    score = abs(crude_impact.get("score", 0))
                    # 더 높은 점수를 가진 기사를 찾거나, 점수가 같으면 첫 번째 기사를 유지
                    if score > best_score or (score > 0 and not best_summary):
                        best_score = score
                        # impact_summary에서 첫 문장만 추출 (너무 길지 않도록)
                        summary_text = article.get("impact_summary", "")
                        if summary_text:
                            first_sentence = summary_text.split(". ")[0]
                            if not first_sentence.endswith("."):
                                first_sentence += "."
                            best_summary = first_sentence
                        else:
                            best_summary = article.get("category", "")
            
            if best_summary:
                crude_drivers[crude] = best_summary
            else:
                crude_drivers[crude] = "특이사항 없음"
        
        return crude_drivers

    # ──────────────────────────────────────────────
    # 메인 생성 로직
    # ──────────────────────────────────────────────
    async def generate_briefing(
        self,
        forecast: ForecastResult,
        classified_articles: List[Dict[str, Any]],
        price_data: Dict[str, Dict[str, float]],
        force: bool = False,
    ) -> Briefing:
        """
        일일 유가 브리핑 생성.
        - 뉴스 기사가 없으면 생성하지 않음 (None 반환 대신 has_news=False 마킹)
        - crude_assessments는 결정론적으로 계산 (LLM 의존 X)
        - LLM은 summary, key_factors, risk_scenarios 등 텍스트만 담당
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # 실제 유가 데이터 기준일 (price_data에서 추출)
        price_data_as_of = str(price_data.get("_data_as_of", ""))
        price_prev_date = str(price_data.get("_prev_date", ""))

        if not force:
            cached_briefing = self._load_from_cache(today)
            if cached_briefing:
                logger.info("Loaded briefing from cache.")
                return cached_briefing

        # ── data_as_of 기준 뉴스 필터링 ──
        # "직전 거래일(_prev_date) 이후에 발행된 뉴스"만 분석 대상으로 삼는다.
        # 예: data_as_of=4/29, prev_date=4/28 → 4/28 이후 뉴스 = 시장에 영향을 준 뉴스
        # 평일: ~24h, 주말/연휴: 자동으로 48~72h 포함
        filtered_articles = classified_articles
        cutoff_date_str = price_prev_date or price_data_as_of
        if cutoff_date_str:
            try:
                cutoff = datetime.strptime(cutoff_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                filtered_articles = []
                for article in classified_articles:
                    article_data = article.get("article", {}) if isinstance(article.get("article"), dict) else article
                    pub = article_data.get("published_at") or article.get("published_at")
                    if pub:
                        try:
                            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                            if dt >= cutoff:
                                filtered_articles.append(article)
                        except (ValueError, TypeError):
                            filtered_articles.append(article)  # 파싱 실패 시 포함
                    else:
                        filtered_articles.append(article)  # 날짜 정보 없으면 포함
                logger.info(f"[Briefing] {cutoff_date_str} 이후 뉴스 필터링: {len(classified_articles)}건 → {len(filtered_articles)}건")
            except ValueError:
                logger.warning(f"[Briefing] cutoff 날짜 파싱 실패: {cutoff_date_str}, 필터링 스킵")

        # 유종별 최근 거래일 시세 결정론적 계산
        crude_assessments = self._compute_crude_assessments(price_data, filtered_articles)

        # 뉴스가 없으면 최소 브리핑만 저장
        relevant_articles = [a for a in filtered_articles if a.get("is_relevant")]
        if not relevant_articles:
            logger.warning("No relevant news articles. Generating minimal briefing.")
            briefing = Briefing(
                date=today,
                data_as_of=price_data_as_of,
                prev_date=price_prev_date,
                summary="금일 분석 대상 뉴스가 수집되지 않아 정성 분석을 수행하지 못했습니다.",
                key_factors=[],
                risk_scenarios=[],
                price_outlook="뉴스 기반 분석 불가. 정량 모델 전망만 참고하시기 바랍니다.",
                crude_assessments=crude_assessments,
                has_news=False,
                generated_at=datetime.now(timezone.utc).isoformat(),
            )
            self._save_to_cache(briefing)
            return briefing

        # LLM 프롬프트 구성 (텍스트 분석만)
        prompt = self._build_briefing_prompt(forecast=forecast, articles=relevant_articles)

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
                        timeout=120.0
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

                # 불필요한 필드 제거 (LLM이 혹시 넣었을 경우)
                response_data.pop("crude_outlooks", None)
                response_data.pop("crude_assessments", None)
                response_data.pop("similar_cases", None)
                response_data.pop("confidence_note", None)

                # ── 분석 대상 기사 메타데이터 추출 ──
                analyzed_articles_meta = []
                for a in relevant_articles:
                    article_data = a.get("article", {}) if isinstance(a.get("article"), dict) else a
                    analyzed_articles_meta.append(AnalyzedArticle(
                        title=a.get("translated_title") or article_data.get("title", "제목 없음"),
                        url=article_data.get("url", ""),
                        source=article_data.get("source_name") or article_data.get("data_source", "알 수 없음"),
                        published_at=article_data.get("published_at", ""),
                        impact_score=a.get("impact_score", 0),
                    ))
                # 영향력 높은 순으로 정렬
                analyzed_articles_meta.sort(key=lambda x: abs(x.impact_score), reverse=True)

                briefing = Briefing(
                    date=today,
                    data_as_of=price_data_as_of,
                    prev_date=price_prev_date,
                    generated_at=datetime.now(timezone.utc).isoformat(),
                    crude_assessments=crude_assessments,
                    has_news=True,
                    analyzed_articles=analyzed_articles_meta,
                    **response_data
                )
                if not self._is_korean_briefing(briefing):
                    logger.warning("LLM returned a non-Korean briefing. Returning minimal briefing.")
                    briefing = self._get_fallback_briefing(today, crude_assessments, price_data_as_of)
                
                self._save_to_cache(briefing)
                return briefing

            except (httpx.HTTPError, ValueError, json.JSONDecodeError, ValidationError) as e:
                logger.error(f"Attempt {attempt + 1}: Failed to generate briefing. Error: {e}")
                if attempt == max_retries:
                    logger.warning("All attempts failed. Returning fallback briefing.")
                    briefing = self._get_fallback_briefing(today, crude_assessments, price_data_as_of)
                    self._save_to_cache(briefing)
                    return briefing

    def _get_fallback_briefing(
        self,
        today: str,
        crude_assessments: List[CrudeDailyAssessment],
        data_as_of: str = "",
    ) -> Briefing:
        from app.schemas.forecast import BriefingKeyFactor, RiskScenario
        return Briefing(
            date=today,
            data_as_of=data_as_of,
            prev_date="", # fallback doesn't easily have prev_date but it's ok
            generated_at=datetime.now(timezone.utc).isoformat(),
            summary="일시적인 AI 분석 지연으로 인해 요약 브리핑을 불러오지 못했습니다.",
            key_factors=[BriefingKeyFactor(category="unknown", description="분석 지연 중임.", impact="neutral", score=0)],
            risk_scenarios=[RiskScenario(scenario="수집/분석 지연", probability="low", price_impact="N/A")],
            price_outlook="정량 모델 기반으로 당분간 밴드 내 변동성을 보일 것으로 예상됨.",
            crude_assessments=crude_assessments,
            has_news=False,
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
        required = [value for value in text_values if value]
        return bool(required) and sum(1 for value in required if self._has_hangul(value)) >= max(1, len(required) // 2)

    def _build_briefing_prompt(self, forecast: ForecastResult,
                               articles: List[Dict[str, Any]]) -> str:
        """브리핑 생성을 위한 프롬프트 — LLM은 텍스트 분석만 담당"""

        articles_str = "\n".join([
            f"- Title: {a.get('article', {}).get('title', 'N/A')}\n  Category: {a.get('category', 'N/A')}, Impact Score: {a.get('impact_score', 0)}\n  Summary: {a.get('impact_summary', 'N/A')}"
            for a in articles
        ][:5])

        prompt = f"""
You are a senior oil market analyst at a top financial institution. Your task is to generate a daily oil price briefing for professional clients. The briefing must be objective, data-driven, and concise.

IMPORTANT: All text values in the JSON output MUST be written in Korean (한국어). Do NOT translate the JSON keys.
IMPORTANT: All description fields MUST use Korean 음슴체 style (e.g. ~함, ~임, ~됨).

Use the provided news data to construct your analysis. You MUST respond ONLY with a valid JSON object in the specified format.

[CONTEXTUAL DATA]

Key News Articles (analyzed with AI):
{articles_str if articles_str else "No significant news in the last 24 hours."}

[TASK]
Based on the news articles, generate a concise daily briefing.
CRITICAL: You must be extremely concise. Keep all text descriptions as short as possible.
- Limit key_factors to max 3 items
- Limit risk_scenarios to max 2 items

[JSON OUTPUT FORMAT]
{{
  "summary": "string (반드시 한국어 음슴체로 작성. 2문장 이내, 100자 이하의 매우 간결한 핵심 요약)",
  "key_factors": [
    {{
      "category": "string (예: '공급', '지정학', '수요' 등 짧은 단어)",
      "description": "string (반드시 한국어 음슴체(~함, ~임)로 작성. 1문장, 50자 이내의 아주 짧은 핵심 설명)",
      "impact": "string ('bullish', 'bearish', 또는 'neutral' 중 하나로 영문 유지)",
      "score": "integer (-5 to 5)"
    }}
  ],
  "risk_scenarios": [
    {{
      "scenario": "string (반드시 한국어로 작성. 1문장, 40자 이내의 짧은 리스크 명칭)",
      "probability": "string ('high', 'medium', 또는 'low' 중 하나로 영문 유지)",
      "price_impact": "string (예: '+$3-5/bbl')"
    }}
  ],
  "price_outlook": "string (반드시 한국어 음슴체로 작성. 1문장, 50자 이내의 종합 방향성 결론)",
  "confidence_note": "string (반드시 한국어 음슴체로 작성. 1문장, 30자 이내의 짧은 코멘트)"
}}
"""
        return prompt
