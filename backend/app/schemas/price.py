from __future__ import annotations
"""
Pydantic 스키마 for Price Data
"""
from typing import Optional
from pydantic import BaseModel


class OilPrice(BaseModel):
    """단일 시점의 유가 정보"""
    date: str  # YYYY-MM-DD
    dubai: Optional[float] = None  # Dubai 현물가 (USD/bbl)
    wti: Optional[float] = None  # WTI 현물가 (USD/bbl)
    brent: Optional[float] = None  # Brent 현물가 (USD/bbl)


class PriceHistory(BaseModel):
    """기간별 유가 히스토리"""
    prices: list[OilPrice]
    source: str = "opinet"
    last_updated: str


class MacroIndicator(BaseModel):
    """단일 시점의 거시경제 지표"""
    date: str
    fed_rate: Optional[float] = None
    dollar_index: Optional[float] = None
    cpi: Optional[float] = None
    industrial_prod: Optional[float] = None
    yield_spread: Optional[float] = None


class MacroHistory(BaseModel):
    """기간별 거시경제 지표 히스토리"""
    indicators: list[MacroIndicator]
    source: str = "fred"
    last_updated: str
