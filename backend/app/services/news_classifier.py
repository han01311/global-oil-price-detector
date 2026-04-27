from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone
import httpx

from pydantic import ValidationError

from app.core.config import settings
from app.schemas.news import NewsArticle, ClassifiedArticle, CrudeImpact
from app.services.market_memory import MarketMemory

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

class NewsClassifier:
    """Ollama (Gemma 4) 기반 뉴스 요인 분류기"""

    CATEGORIES = ["geopolitics", "supply", "demand", "macro", "climate", "speculation"]
    CRUDE_TYPES = ["dubai", "brent", "wti"]
    CONCURRENCY_LIMIT = 5

    def __init__(self, ollama_url: str | None = None):
        self.ollama_url = (ollama_url or settings.LOCAL_LLM_URL).rstrip("/")
        self.model_name = "gemma"
        self.semaphore = asyncio.Semaphore(self.CONCURRENCY_LIMIT)

    def _build_classification_prompt(self, article_content: str) -> str:
        """분류용 프롬프트 생성 — 유종별 독립 영향도 평가 포함"""
        category_definitions = """
- geopolitics (지정학): 전쟁, 제재, 외교 분쟁, 선거 등 국가 간 관계 및 정치적 사건. (예: 이스라엘-하마스 전쟁, 이란 핵 협상, 러시아-우크라이나 전쟁)
- supply (공급): OPEC+ 회의, 감산/증산, 셰일 오일 생산량, 원유 재고, 시추 리그 수, 수송 차질 등 공급량에 직접적 영향을 주는 요인. (예: 사우디 자발적 감산, 미국 원유 재고 급증)
- demand (수요): 경기 침체/회복, 계절적 수요(난방유, 드라이빙 시즌), 중국 경제 지표, 항공유 수요 등 수요량에 직접적 영향을 주는 요인. (예: 중국 제조업 PMI 호조, IEA 월간 수요 전망)
- macro (거시경제): 금리, 달러 인덱스, 인플레이션, 주요국 통화정책 등 석유 시장 외적인 경제 환경 요인. (예: 미국 연준 금리 인상, 달러 강세)
- climate (기후/ESG): 허리케인 등 기상 이변, 탄소 중립 정책, 신재생에너지 전환, ESG 투자 동향 등. (예: 멕시코만 허리케인으로 인한 생산 차질, 파리 기후 협약)
- speculation (투기/심리): 선물 시장 투기적 포지션, 시장 참여자 심리, 기술적 분석 등. (예: WTI 선물 순매수 포지션 증가)
"""

        impact_score_guide = """
- +5: 주요 산유국 간 대규모 전쟁 발발, 호르무즈 해협 봉쇄 등 공급에 즉각적이고 심각한 충격을 주는 사건.
- +3: OPEC+의 예상 밖 대규모 감산, 주요 산유국 생산 차질 장기화.
- +1: 지정학적 긴장 고조 발언, 예상보다 낮은 원유 재고.
- 0: 유가에 미치는 영향이 중립적이거나 불확실함.
- -1: 지정학적 긴장 완화, 예상보다 높은 원유 재고.
- -3: OPEC+의 예상 밖 대규모 증산, 글로벌 경기 침체 우려 심화.
- -5: 이란 핵 협상 타결로 인한 대규모 공급 재개, 심각한 글로벌 금융위기 발생.
"""

        crude_sensitivity_guide = """
Each crude type has different geopolitical sensitivities. Evaluate impact INDEPENDENTLY for each:

- Dubai Crude: Most sensitive to Middle East geopolitics (Iran, Hormuz Strait, Saudi Arabia, OPEC+ cuts), Asian demand (China, India, Japan), and Gulf state production policies.
- Brent Crude: Most sensitive to European energy policy, Russia-Ukraine conflict, Libyan production, North Sea supply disruptions, and global benchmark sentiment.
- WTI Crude: Most sensitive to US shale production, SPR releases, Gulf of Mexico hurricanes, US interest rates/dollar strength, Cushing storage levels, and US domestic policy.

Example: A Hormuz Strait tension event → Dubai: +4 (direct supply route threat), Brent: +2 (global supply concern), WTI: +1 (indirect sentiment only).
Example: US shale production surge → WTI: -3 (direct oversupply), Brent: -1 (global sentiment), Dubai: 0 (minimal direct impact).
"""

        return f"""
You are an expert financial analyst specializing in the global oil market. Your task is to analyze a news article and classify it based on its potential impact on crude oil prices.

CRITICAL: You must evaluate the impact on EACH crude type (Dubai, Brent, WTI) INDEPENDENTLY, as they have different geopolitical sensitivities.

Follow these instructions precisely:
1.  Read the provided news article content.
2.  Determine if the article is relevant to the global oil price. If it's about local gasoline prices, company stock prices, or other unrelated topics, set `is_relevant` to `false`.
3.  If relevant, identify the primary category that best describes the news. The categories are:
{category_definitions}
4.  Identify any secondary categories if applicable.
5.  For EACH crude type (dubai, brent, wti), independently assess:
    - direction: "bullish", "bearish", or "neutral"
    - score: -5 to +5 using the guide below
    - rationale: A concise explanation in Korean of WHY this crude type is affected differently
{impact_score_guide}

Use this guide for crude-specific sensitivity:
{crude_sensitivity_guide}

6.  Set the overall `impact_score` to the maximum absolute score among the three crude types.
7.  Write a highly insightful `impact_summary` in Korean (1-2 sentences). Do not just summarize the article. Instead, specifically analyze HOW and WHY the events described in the article will affect global oil prices or market dynamics, providing professional market insights.
8.  Provide a `confidence` score (0.0 to 1.0) for your overall classification.
9.  Translate the original article title into natural Korean and provide it as `translated_title`.
10. You MUST respond ONLY with a valid JSON object in the specified format. Do not include any other text, explanations, or markdown formatting.

Article Content to Analyze:
---
{article_content}
---

JSON Output Format:
{{
  "is_relevant": boolean,
  "category": "string (one of {', '.join(self.CATEGORIES)})",
  "sub_categories": ["string"],
  "impact_by_crude": {{
    "dubai": {{"direction": "string", "score": integer, "rationale": "string (in Korean)"}},
    "brent": {{"direction": "string", "score": integer, "rationale": "string (in Korean)"}},
    "wti": {{"direction": "string", "score": integer, "rationale": "string (in Korean)"}}
  }},
  "impact_score": integer (-5 to 5),
  "impact_summary": "string (in Korean)",
  "confidence": float (0.0 to 1.0),
  "translated_title": "string (in Korean)"
}}
"""

    async def classify_article(self, article: dict) -> ClassifiedArticle | None:
        """단일 기사를 분류하고 유종별 영향도를 독립 평가한다"""
        async with self.semaphore:
            try:
                article_model = NewsArticle(**article)
            except ValidationError as e:
                logger.error(f"Invalid article format: {e}")
                return None

            content_to_analyze = f"Title: {article_model.title}\nDescription: {article_model.description or ''}\nContent Snippet: {article_model.content_snippet or ''}"
            prompt = self._build_classification_prompt(content_to_analyze)

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
                    response_json = json.loads(response.json()["response"])

                # Parse impact_by_crude from response
                raw_impact = response_json.pop("impact_by_crude", {})
                impact_by_crude = {}
                for crude_type in self.CRUDE_TYPES:
                    if crude_type in raw_impact:
                        try:
                            impact_by_crude[crude_type] = CrudeImpact(**raw_impact[crude_type])
                        except (ValidationError, TypeError):
                            impact_by_crude[crude_type] = CrudeImpact()
                    else:
                        # Fallback: use overall impact_score for all crude types
                        overall_score = response_json.get("impact_score", 0)
                        direction = "bullish" if overall_score > 0 else ("bearish" if overall_score < 0 else "neutral")
                        impact_by_crude[crude_type] = CrudeImpact(
                            direction=direction, score=overall_score,
                            rationale=response_json.get("impact_summary", "")
                        )

                result_data = {
                    "article": article_model,
                    "classified_at": datetime.now(timezone.utc).isoformat(),
                    "impact_by_crude": impact_by_crude,
                    **response_json
                }
                
                classified_article = ClassifiedArticle(**result_data)
                return classified_article

            except httpx.HTTPError as e:
                logger.error(f"Ollama API request failed for article '{article_model.title}': {e}")
                return None
            except (json.JSONDecodeError, ValidationError) as e:
                resp_text = response.text if 'response' in locals() else 'N/A'
                logger.error(f"Failed to parse or validate Gemma 4 response for article '{article_model.title}': {e}\nResponse text: {resp_text}")
                return None
            except Exception as e:
                logger.error(f"An unexpected error occurred during classification for article '{article_model.title}': {e}")
                return None

    async def classify_batch(self, articles: list[dict]) -> list[ClassifiedArticle]:
        """여러 기사를 배치로 분류 (rate limit 고려 및 기분류 기사 스킵)"""
        if not articles:
            return []

        memory = MarketMemory()
        existing_ids = set()
        
        # Check which articles are already in memory
        if memory.is_available():
            article_ids = []
            for article in articles:
                try:
                    # Validate to get the ID safely
                    model = NewsArticle(**article)
                    article_ids.append(model.id)
                except:
                    pass
            
            if article_ids:
                try:
                    # Fetch existing from ChromaDB
                    existing_data = memory._collection.get(ids=article_ids, include=["metadatas", "documents"])
                    if existing_data and existing_data.get('ids'):
                        existing_ids = set(existing_data['ids'])
                except Exception as e:
                    logger.error(f"Failed to check existing articles in MarketMemory: {e}")

        tasks = []
        skipped_results = []
        
        for article in articles:
            try:
                model = NewsArticle(**article)
                if model.id in existing_ids:
                    # Reconstruct from memory if possible, or just skip if we don't strictly need it.
                    # Since the frontend needs the full list, let's try to reconstruct it.
                    idx = existing_data['ids'].index(model.id)
                    meta = existing_data['metadatas'][idx]
                    doc = existing_data['documents'][idx]
                    
                    # Reconstruct impact_by_crude from metadata
                    impact_by_crude = {}
                    for crude in self.CRUDE_TYPES:
                        if f"{crude}_score" in meta:
                            impact_by_crude[crude] = CrudeImpact(
                                score=meta.get(f"{crude}_score", 0),
                                direction=meta.get(f"{crude}_direction", "neutral"),
                                rationale=meta.get(f"{crude}_rationale", "")
                            )
                            
                    # Basic reconstruction
                    reconstructed = ClassifiedArticle(
                        article=model,
                        is_relevant=True,
                        category=meta.get('category', 'unknown'),
                        sub_categories=[],
                        impact_score=meta.get('impact_score', 0),
                        impact_summary=doc.split('\nSummary: ')[-1] if '\nSummary: ' in doc else '',
                        confidence=meta.get('confidence', 0.8),
                        classified_at=datetime.now(timezone.utc).isoformat(),
                        impact_by_crude=impact_by_crude,
                        translated_title=meta.get('translated_title')
                    )
                    skipped_results.append(reconstructed)
                    continue
            except:
                pass
                
            tasks.append(self.classify_article(article))
            
        logger.info(f"Classifying {len(tasks)} new articles. Skipping {len(skipped_results)} already classified.")
        
        results = []
        if tasks:
            results = await asyncio.gather(*tasks)
        
        valid_results = [result for result in results if result is not None]
        return valid_results + skipped_results
