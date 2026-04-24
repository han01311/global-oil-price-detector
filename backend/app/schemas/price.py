"""
Pydantic 스키마 for Price Data
"""
from pydantic import BaseModel


class OilPrice(BaseModel):
    """단일 시점의 유가 정보"""
    date: str  # YYYY-MM-DD
    wti: float | None = None  # WTI 현물가 (USD/bbl)
    brent: float | None = None  # Brent 현물가 (USD/bbl)


class PriceHistory(BaseModel):
    """기간별 유가 히스토리"""
    prices: list[OilPrice]
    source: str = "eia"
    last_updated: str
