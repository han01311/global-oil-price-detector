export interface FactorBreakdown {
  category: string;
  contribution: number;
  article_count: number;
}

export interface CrudeForecast {
  crude_type: string; // "dubai" | "brent" | "wti"
  current_price: number;
  estimated_7d: number;
  estimated_7d_high: number;
  estimated_7d_low: number;
  estimated_30d: number;
  estimated_30d_high: number;
  estimated_30d_low: number;
  baseline_change_7d: number;
  baseline_change_30d: number;
  news_adjustment_pct: number;
  confidence: number; // 0.0 to 1.0
  dominant_factor: string | null;
}

export interface ForecastResult {
  current_price: number;
  estimated_7d: number;
  estimated_7d_high: number;
  estimated_7d_low: number;
  estimated_30d: number;
  estimated_30d_high: number;
  estimated_30d_low: number;
  baseline_change_7d: number;
  baseline_change_30d: number;
  news_adjustment_pct: number;
  confidence: number; // 0.0 to 1.0
  dominant_factor: string | null;
  extreme_volatility_warning?: boolean;
  factor_breakdown: FactorBreakdown[];
  forecasts_by_crude: Record<string, CrudeForecast>; // {"dubai": ..., "brent": ..., "wti": ...}
  generated_at: string;
}

export interface BriefingKeyFactor {
  category: string;
  description: string;
  impact: 'bullish' | 'bearish' | 'neutral';
  score: number; // -5 to 5
}

export interface RiskScenario {
  scenario: string;
  probability: 'high' | 'medium' | 'low';
  price_impact: string;
}

export interface SimilarCase {
  event: string;
  date: string;
  similarity: number;
  actual_impact: string;
}

export interface CrudeOutlook {
  crude_type: string; // "dubai" | "brent" | "wti"
  direction: 'bullish' | 'bearish' | 'neutral';
  summary: string;
  key_driver: string;
}

export interface Briefing {
  date: string;
  summary: string;
  key_factors: BriefingKeyFactor[];
  risk_scenarios: RiskScenario[];
  similar_cases: SimilarCase[];
  price_outlook: string;
  confidence_note: string;
  crude_outlooks: CrudeOutlook[]; // 유종별 독립 전망
  generated_at: string;
}
