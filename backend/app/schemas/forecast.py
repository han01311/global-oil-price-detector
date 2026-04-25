from pydantic import BaseModel, Field
from typing import List, Optional

class FactorBreakdown(BaseModel):
    category: str
    contribution: float = Field(..., description="This factor's contribution to the news adjustment pct.")
    article_count: int


class CrudeForecast(BaseModel):
    """단일 유종의 독립 예측 결과"""
    crude_type: str                   # "dubai" | "brent" | "wti"
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
    dominant_factor: Optional[str] = None


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
    extreme_volatility_warning: bool = Field(False, description="Indicates extreme market volatility (Black Swan).")

    factor_breakdown: List[FactorBreakdown]

    # 유종별 독립 예측 (하위호환: 빈 dict면 기존 WTI 단일 결과 사용)
    forecasts_by_crude: dict[str, CrudeForecast] = {}

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


class CrudeOutlook(BaseModel):
    """유종별 독립 전망"""
    crude_type: str         # "dubai" | "brent" | "wti"
    direction: str          # "bullish" | "bearish" | "neutral"
    summary: str            # 해당 유종의 전망 요약
    key_driver: str         # 핵심 동인


class Briefing(BaseModel):
    date: str
    summary: str                          # 3줄 핵심 요약
    key_factors: list[BriefingKeyFactor]   # 주요 요인 (최대 5개)
    risk_scenarios: list[RiskScenario]     # 리스크 시나리오 (최대 3개)
    similar_cases: list[SimilarCase]       # 과거 유사 사례 (최대 3개)
    price_outlook: str                     # 가격 방향성 전망
    confidence_note: str                   # 신뢰도/한계 코멘트
    # 유종별 독립 전망 (하위호환: 빈 리스트면 기존 통합 전망 사용)
    crude_outlooks: list[CrudeOutlook] = []
    generated_at: str

