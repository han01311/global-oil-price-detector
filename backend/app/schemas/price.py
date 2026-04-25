"""
Pydantic 스키마 for Price Data
"""
from pydantic import BaseModel


class OilPrice(BaseModel):
    """단일 시점의 유가 정보"""
    date: str  # YYYY-MM-DD
    dubai: float | None = None  # Dubai 현물가 (USD/bbl)
    wti: float | None = None  # WTI 현물가 (USD/bbl)
    brent: float | None = None  # Brent 현물가 (USD/bbl)


class PriceHistory(BaseModel):
    """기간별 유가 히스토리"""
    prices: list[OilPrice]
    source: str = "opinet"
    last_updated: str


class MacroIndicator(BaseModel):
    """단일 시점의 거시경제 지표"""
    date: str
    fed_rate: float | None = None
    dollar_index: float | None = None
    cpi: float | None = None
    industrial_prod: float | None = None
    yield_spread: float | None = None


class MacroHistory(BaseModel):
    """기간별 거시경제 지표 히스토리"""
    indicators: list[MacroIndicator]
    source: str = "fred"
    last_updated: str
