"""
Pydantic 스키마 for News Data
"""
from pydantic import BaseModel, Field


class NewsArticle(BaseModel):
    """단일 뉴스 기사 정보"""
    id: str                      # hash(url)
    title: str
    description: str | None
    source: str | None           # 출처 (Reuters, Bloomberg 등)
    url: str
    published_at: str            # ISO 8601
    content_snippet: str | None  # 본문 일부
    data_source: str             # "newsapi" | "gdelt"


class NewsCollection(BaseModel):
    """뉴스 기사 모음"""
    articles: list[NewsArticle]
    query_keywords: list[str]
    collected_at: str
    total_count: int


class ClassifiedArticle(BaseModel):
    """분류가 완료된 뉴스 기사"""
    article: NewsArticle
    is_relevant: bool
    category: str
    sub_categories: list[str] = []
    impact_score: int = Field(..., ge=-5, le=5)
    impact_summary: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    classified_at: str               # ISO 8601


class SimilarEvent(BaseModel):
    """유사 과거 사례"""
    title: str
    summary: str
    category: str
    impact_score: int
    date: str
    url: str
    wti_change_1d: float | None
    wti_change_7d: float | None
    wti_change_30d: float | None
    similarity: float = Field(..., ge=0.0, le=1.0)

class FactorScore(BaseModel):
    """요인별 점수"""
    category: str
    avg_score: float           # 평균 Impact Score
    article_count: int         # 기사 수
    trend: str                 # "bullish" | "bearish" | "neutral"

class FactorSummary(BaseModel):
    """요인 종합"""
    factors: list[FactorScore]
    overall_sentiment: float   # 종합 감성 (-5 ~ +5)
    updated_at: str
