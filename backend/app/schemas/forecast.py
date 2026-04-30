from __future__ import annotations
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


# ──────────────────────────────────────────────
# Method B: 펀더멘탈 분석 모델 스키마
# ──────────────────────────────────────────────

class FundamentalSignal(BaseModel):
    """개별 시그널 결과"""
    signal_id: str                    # "inventory" | "production" | "seasonal" | "mean_reversion" | "dollar"
    name: str                         # 한국어 표시명
    change: Optional[float] = None    # 예상 변동률 (0.01 = 1%)
    confidence: float = 0.0           # 신뢰도 (0.0 ~ 1.0)
    weight: float = 0.0              # 최종 합산 시 가중치 비율
    detail: str = ""                  # 근거 설명 텍스트


class FundamentalCrudeForecast(BaseModel):
    """Method B 유종별 예측 결과"""
    crude_type: str
    current_price: float
    estimated_7d: float
    estimated_7d_high: float
    estimated_7d_low: float
    total_change_pct: float           # 총 변동률 (%)
    signals: List[FundamentalSignal]   # 각 시그널의 기여도
    confidence: float = Field(..., ge=0.0, le=1.0)


class FundamentalForecastResult(BaseModel):
    """Method B 전체 결과"""
    forecasts_by_crude: dict[str, FundamentalCrudeForecast] = {}
    method: str = "fundamental"
    generated_at: str


# ──────────────────────────────────────────────
# 이중 방법론 비교 스키마
# ──────────────────────────────────────────────

class DualForecastResult(BaseModel):
    """두 방법론의 예측 결과를 나란히 제공"""
    method_a: ForecastResult                   # 기술적 분석 (XGBoost + 뉴스 보정)
    method_b: FundamentalForecastResult         # 펀더멘탈 분석 (수급 기반)
    consensus: bool = False                     # 두 방법이 같은 방향인지
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

class CrudeDailyAssessment(BaseModel):
    """유종별 당일 시세 평가 — 실제 가격 등락 기반"""
    crude_type: str         # "dubai" | "brent" | "wti"
    direction: str          # "bullish" | "bearish" | "neutral"
    change_pct: float       # 전일 대비 변동률 (%)
    key_driver: str         # 핵심 상승/하락 요인 키워드


class Briefing(BaseModel):
    date: str
    summary: str                          # 핵심 요약
    key_factors: list[BriefingKeyFactor]   # 주요 요인 (최대 3개)
    risk_scenarios: list[RiskScenario]     # 리스크 시나리오 (최대 2개)
    price_outlook: str                     # 가격 방향성 결론
    confidence_note: str                   # 신뢰도/한계 코멘트
    crude_assessments: list[CrudeDailyAssessment] = []  # 유종별 당일 시세 평가
    has_news: bool = True                 # 뉴스 기사 기반 여부
    generated_at: str

