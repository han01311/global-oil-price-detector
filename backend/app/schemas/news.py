"""
Pydantic 스키마 for News Data
"""
from pydantic import BaseModel


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
