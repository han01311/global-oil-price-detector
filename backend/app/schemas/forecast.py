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
