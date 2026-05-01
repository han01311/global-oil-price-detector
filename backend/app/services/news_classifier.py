from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone
import httpx
import re
from bs4 import BeautifulSoup

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
    CONCURRENCY_LIMIT = 2

    def __init__(self, ollama_url: str | None = None):
        self.ollama_url = (ollama_url or settings.LOCAL_LLM_URL).rstrip("/")
        self.model_name = "gemma4:e4b"
        self.semaphore = asyncio.Semaphore(self.CONCURRENCY_LIMIT)

    async def _fetch_title_from_url(self, url: str) -> str | None:
        """Fetch the original title from the article URL using BeautifulSoup."""
        if not url: return None
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10.0, follow_redirects=True)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    if soup.title and soup.title.string:
                        return soup.title.string.strip()
        except Exception as e:
            logger.warning(f"Failed to fetch title from {url}: {e}")
        return None

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
## Impact Score Rubric (-5 to +5)
- +5/-5 (Extreme): Physical supply disruption/surplus >2 mb/d, or system-wide demand collapse/surge. (e.g., Hormuz closure, Covid-level crash).
- +4/-4 (Very High): Physical supply shift of 0.5-2 mb/d, or credible threat of imminent disruption. (e.g., Major pipeline sabotage, US sanctions).
- +3/-3 (High): Significant tightening/oversupply signal beyond consensus. (e.g., OPEC+ surprise cut/increase >500k bpd).
- +2/-2 (Moderate): Notable shift or geopolitical escalation. (e.g., US inventory draw >5m bbl, rig count changes, minor attacks).
- +1/-1 (Mild): Marginal sentiment-driven shift, or verbal escalation without physical impact.
- 0 (Neutral): Priced in, mixed signals, or routine events.
"""

        crude_sensitivity_guide = """
## Crude Sensitivity Guide (Evaluate each INDEPENDENTLY)

- Dubai: Most sensitive to Middle East geopolitics (Iran, Hormuz, Saudi), Asian demand (China teapots, India), and Saudi OSP.
- Brent: Most sensitive to European energy policy, Russia-Ukraine, Libya/Nigeria disruptions, and global benchmark sentiment.
- WTI: Most sensitive to US shale production (Permian), Cushing storage levels, SPR releases, Gulf of Mexico hurricanes, and US Fed rates/Dollar (DXY).

Example: Hormuz Strait threat → Dubai: +4 (direct transit route), Brent: +3 (global risk), WTI: +1 (sentiment only).
Example: US Fed hikes rates unexpectedly → WTI: -2 (direct dollar impact), Brent: -1 (partial), Dubai: -1.
"""

        return f"""
You are an expert financial analyst specializing in the global oil market. Your task is to analyze a news article and classify it based on its potential impact on crude oil prices.

CRITICAL: You must evaluate the impact on EACH crude type (Dubai, Brent, WTI) INDEPENDENTLY, as they have different geopolitical sensitivities.

Follow these instructions precisely:
1.  Read the provided news article content.
2.  Determine if the article is relevant to the global oil price. 
    **EXCLUSION RULES (Set `is_relevant` to `false` if ANY apply):**
    - Local news: Local gas station prices, minor regional power outages, local weather not affecting oil infrastructure.
    - Corporate news: Earnings reports, stock price movements, or executive changes of individual companies (e.g., Exxon, Tesla, airline companies) UNLESS they are major national oil companies (Saudi Aramco) or represent a massive global industry shift.
    - General market recaps: Daily summaries of S&P500 or general stock market indices that simply mention "oil prices rose" in passing without analyzing the cause.
    - Unrelated topics: Articles about cooking oil, olive oil, essential oils, or unrelated political scandals.
3.  If relevant, identify the primary category that best describes the news. The categories are:
{category_definitions}
4.  Identify any secondary categories if applicable.

5.  For EACH crude type (dubai, brent, wti), independently assess:
    - direction: "bullish", "bearish", or "neutral"
    - score: -5 to +5 using the Impact Score Rubric above
    - rationale: Write in Korean. This MUST be a specific, evidence-based explanation (2-3 sentences) of WHY this particular crude type is affected. You MUST:
      * Reference the specific pricing mechanism or key price variable from the Crude-Specific Sensitivity Guide that makes this crude type sensitive (or insensitive) to this event
      * Explain the causal transmission path: Event → [specific market mechanism] → Price impact
      * If the score differs from other crude types, explicitly explain WHY the differential exists
      * NEVER write a generic statement like "유가에 영향을 줄 수 있다" — always specify the concrete channel of impact
{impact_score_guide}

Use this guide for crude-specific sensitivity:
{crude_sensitivity_guide}

## Output Field Instructions

6.  `impact_score`: Set to the maximum ABSOLUTE value among the three crude type scores.

7.  `impact_summary` (CRITICAL — this is the most important output field):
    Write a professional-grade analytical commentary in Korean, following this structure:

    **Length**: 3-5 sentences (approximately 150-300 Korean characters). This is NOT a simple summary.

    **Structure** (follow this 3-part framework):
    ① [사건 식별] 기사에서 보도된 핵심 사건/데이터를 1문장으로 정확히 기술. 기사에 명시된 구체적 수치, 인명, 기관명, 날짜를 반드시 포함할 것.
    ② [전파 경로] 이 사건이 글로벌 원유 시장에 영향을 미치는 구체적인 전파 경로(transmission mechanism)를 분석. 공급/수요/심리 중 어떤 채널을 통해 유가에 작용하는지 명시할 것.
    ③ [시장 전망] 단기(1-7일) 유가에 대한 방향성과 강도를 판단하되, 불확실성이 높은 경우 시나리오를 구분하여 기술할 것.

    **Anti-Hallucination Rules**:
    - 기사 본문에 명시적으로 언급된 사실(fact)만을 근거로 분석할 것
    - 기사에 없는 수치, 날짜, 발언, 기관의 입장을 절대 만들어내지 말 것
    - 인과관계가 불확실한 경우 "~할 가능성이 있다", "~여부가 관건이다" 등 불확실성을 명시적으로 표현할 것
    - 기사의 정보가 불충분한 경우, 무리하게 확대 해석하지 말고 기사에 제시된 범위 내에서만 분석할 것
    - "전문가들은 ~라고 분석했다" 등의 허위 인용을 절대 생성하지 말 것

    **Quality Standard Example** (Good):
    "사우디 에너지부가 아시아향 아랍 라이트 7월 OSP를 배럴당 $1.80 인상한다고 발표했다. 이는 아시아 정유사들의 원유 조달 비용을 직접적으로 상승시키며, 특히 중국 독립 정유사(teapot)들의 마진 압박으로 이어져 두바이유 현물 프리미엄 확대가 예상된다. 다만 동시에 아시아 수요 둔화 우려가 상존하는 만큼, 실제 가격 상승폭은 $0.50-1.00/bbl 수준에 그칠 가능성이 높다."

    **Quality Standard Example** (Bad — DO NOT write like this):
    "이 기사는 사우디의 유가 정책에 대해 보도하고 있으며, 전반적으로 유가에 상승 압력을 줄 것으로 보입니다."

8.  `confidence` (0.0 to 1.0): Rate your confidence in the overall classification based on:
    - 0.9-1.0: Article contains specific data points, official statements, or confirmed events with clear oil market implications
    - 0.7-0.8: Article describes a developing situation with probable but not certain oil market impact
    - 0.5-0.6: Article is tangentially related to oil; impact direction is ambiguous or speculative
    - 0.3-0.4: Very limited information; classification is largely inference-based
    - Below 0.3: Insufficient information to make a meaningful assessment

9.  `translated_title`: If the original article is in a foreign language (e.g., English, Chinese, Arabic), translate the title into natural, fluent Korean. Preserve proper nouns (OPEC, WTI, EIA etc.) and technical terms. If the article is ALREADY in Korean, set this to `null`. NEVER return an empty string "" — use either a valid Korean translation or `null`.

10. You MUST respond ONLY with a valid JSON object in the specified format. Do not include any other text, explanations, markdown formatting, or code block markers.

Article Content to Analyze:
---
{article_content}
---

JSON Output Format:
{{
  "is_relevant": boolean,
  "category": "string (one of {', '.join(self.CATEGORIES)})",
  "sub_categories": ["string (MUST be in Korean)"],
  "impact_by_crude": {{
    "dubai": {{"direction": "string", "score": integer, "rationale": "string (in Korean, 2-3 sentences, evidence-based)"}},
    "brent": {{"direction": "string", "score": integer, "rationale": "string (in Korean, 2-3 sentences, evidence-based)"}},
    "wti": {{"direction": "string", "score": integer, "rationale": "string (in Korean, 2-3 sentences, evidence-based)"}}
  }},
  "impact_score": integer,
  "impact_summary": "string (in Korean, 3-5 sentences following the 3-part framework above)",
  "confidence": float,
  "translated_title": "string or null"
}}
"""

    async def classify_article(self, article: dict) -> dict:
        """단일 기사를 분류하고 유종별 영향도를 독립 평가한다"""
        async with self.semaphore:
            if "source" not in article and "source_name" in article:
                article["source"] = article["source_name"]
            try:
                article_model = NewsArticle(**article)
            except ValidationError as e:
                err_msg = f"Invalid article format: {e}"
                logger.error(err_msg)
                return {"status": "error", "article_id": article.get("id"), "error": err_msg}

            # Title Validation
            bad_titles = ["untitled", "no title", ""]
            current_title_clean = article_model.title.strip().lower()
            if not current_title_clean or current_title_clean in bad_titles or len(current_title_clean) < 5:
                fetched_title = await self._fetch_title_from_url(article_model.url)
                if fetched_title:
                    article_model.title = fetched_title
                    logger.info(f"Re-fetched 'Untitled' article title from URL: {fetched_title}")
                else:
                    # Fallback to snippet/description
                    fallback_text = article_model.content_snippet or article_model.description or "알 수 없는 기사"
                    article_model.title = fallback_text.split('.')[0][:100] + "..."
                    logger.info(f"Fallback title used: {article_model.title}")

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
                        timeout=120.0
                    )
                    response.raise_for_status()
                    response_json = json.loads(response.json()["response"])

                # Translation Validation (Retry if English)
                def is_korean(text):
                    if not text: return False
                    return len(re.findall(r'[가-힣]', text)) > 3

                original_is_kor = is_korean(article_model.title)
                if not original_is_kor:
                    tt = response_json.get("translated_title", "")
                    if not tt or not is_korean(tt) or (len(re.findall(r'[a-zA-Z]', tt)) > len(re.findall(r'[가-힣]', tt))):
                        logger.warning(f"Translation failed for '{article_model.title}'. Retrying translation only.")
                        retry_prompt = f"Translate the following news title into natural Korean. Output ONLY the translated Korean string, nothing else. Title: {article_model.title}"
                        try:
                            async with httpx.AsyncClient() as client:
                                retry_res = await client.post(
                                    f"{self.ollama_url}/api/generate",
                                    json={
                                        "model": self.model_name,
                                        "prompt": retry_prompt,
                                        "stream": False
                                    },
                                    timeout=15.0
                                )
                                retry_res.raise_for_status()
                                new_title = retry_res.json()["response"].strip().strip('"').strip()
                                if is_korean(new_title):
                                    response_json["translated_title"] = new_title
                        except Exception as e:
                            logger.error(f"Retry translation failed: {e}")

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

                # Ensure required fields are not None
                if response_json.get("category") is None:
                    response_json["category"] = "Uncategorized"
                if response_json.get("impact_summary") is None:
                    response_json["impact_summary"] = "관련성 없음으로 제외됨" if not response_json.get("is_relevant") else "요약 없음"
                if response_json.get("impact_score") is None:
                    response_json["impact_score"] = 0
                if response_json.get("confidence") is None:
                    response_json["confidence"] = 0.0

                result_data = {
                    "article": article_model,
                    "classified_at": datetime.now(timezone.utc).isoformat(),
                    "impact_by_crude": impact_by_crude,
                    **response_json
                }
                
                classified_article = ClassifiedArticle(**result_data)
                return {"status": "success", "result": classified_article}

            except httpx.HTTPError as e:
                err_msg = f"Ollama API request failed: {e}"
                logger.error(f"{err_msg} for article '{article_model.title}'")
                return {"status": "error", "article_id": article_model.id, "error": err_msg}
            except (json.JSONDecodeError, ValidationError) as e:
                resp_text = response.text if 'response' in locals() else 'N/A'
                err_msg = f"Failed to parse or validate Gemma 4 response: {e}"
                logger.error(f"{err_msg} for article '{article_model.title}'\nResponse text: {resp_text}")
                return {"status": "error", "article_id": article_model.id, "error": err_msg}
            except Exception as e:
                err_msg = f"An unexpected error occurred: {e}"
                logger.error(f"{err_msg} for article '{article_model.title}'")
                return {"status": "error", "article_id": article_model.id, "error": err_msg}

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
            if "source" not in article and "source_name" in article:
                article["source"] = article["source_name"]
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
        
        valid_results = [result["result"] for result in results if result and result.get("status") == "success"]
        failed_results = [result for result in results if result and result.get("status") == "error"]
        
        if valid_results or failed_results:
            try:
                from sqlalchemy import update
                from app.core.database import get_session_factory
                from app.models.news_article import NewsArticle as NewsArticleModel
                
                SessionLocal = get_session_factory()
                async with SessionLocal() as db_session:
                    for res in valid_results:
                        # If irrelevant, we store it as -2 so it is hidden from the dashboard but kept for URL deduplication
                        classified_status = 1 if res.is_relevant else -2
                        await db_session.execute(
                            update(NewsArticleModel)
                            .where(NewsArticleModel.id == res.article.id)
                            .values(
                                is_classified=classified_status,
                                classification_result=res.model_dump(),
                                classification_error=None
                            )
                        )
                    for res in failed_results:
                        await db_session.execute(
                            update(NewsArticleModel)
                            .where(NewsArticleModel.id == res["article_id"])
                            .values(
                                is_classified=-1,
                                classification_error=res["error"]
                            )
                        )
                    await db_session.commit()
                    logger.info(f"Updated {len(valid_results)} success, {len(failed_results)} failures in SQLite.")
                    
                    # Store relevant articles to MarketMemory for FactorGauge to pick up
                    if memory.is_available():
                        from app.core.database import Database
                        db_instance = Database()
                        for res in valid_results:
                            if res.is_relevant:
                                price_changes = await db_instance.get_historical_price_changes(res.article.published_at)
                                await memory.store_event(res.model_dump(), price_changes)
                        logger.info(f"Stored valid articles into MarketMemory.")
                        
            except Exception as e:
                logger.error(f"Failed to update database with classification results: {e}")

        return valid_results + skipped_results
