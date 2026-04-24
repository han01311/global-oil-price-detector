from pydantic import BaseModel, Field
from typing import List, Optional

class FactorBreakdown(BaseModel):
    category: str
    contribution: float = Field(..., description="This factor's contribution to the news adjustment pct.")
    article_count: int

class ForecastResult(BaseModel):
    current_price: float
    
    estimated_7d: float
    estimated_7d_high: float
    estimated_7d_low: float
    
    estimated_30d: float
    estimated_30d_high: float
    estimated_30d_low: float
    
    baseline_change_7d: float
    baseline_change_30d: float
    
    news_adjustment_pct: float
    
    confidence: float = Field(..., ge=0.0, le=1.0)
    dominant_factor: Optional[str] = Field(None, description="The most influential news category.")
    
    factor_breakdown: List[FactorBreakdown]
    
    generated_at: str


class BriefingKeyFactor(BaseModel):
    category: str           # 6대 카테고리
    description: str        # 요인 설명
    impact: str             # "bullish" | "bearish" | "neutral"
    score: int              # -5 ~ +5

class RiskScenario(BaseModel):
    scenario: str           # 시나리오 설명
    probability: str        # "high" | "medium" | "low"
    price_impact: str       # 예: "+$3~5"

class SimilarCase(BaseModel):
    event: str              # 과거 이벤트명
    date: str
    similarity: float
    actual_impact: str      # 당시 실제 유가 변동

class Briefing(BaseModel):
    date: str
    summary: str                          # 3줄 핵심 요약
    key_factors: list[BriefingKeyFactor]   # 주요 요인 (최대 5개)
    risk_scenarios: list[RiskScenario]     # 리스크 시나리오 (최대 3개)
    similar_cases: list[SimilarCase]       # 과거 유사 사례 (최대 3개)
    price_outlook: str                     # 가격 방향성 전망
    confidence_note: str                   # 신뢰도/한계 코멘트
    generated_at: str
