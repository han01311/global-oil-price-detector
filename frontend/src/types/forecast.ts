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
  data_as_of?: string;   // 유가 데이터의 마지막 날짜 (e.g. "2026-04-29")
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

export interface CrudeDailyAssessment {
  crude_type: string; // "dubai" | "brent" | "wti"
  direction: 'bullish' | 'bearish' | 'neutral';
  change_pct: number; // 전일 대비 변동률 (%)
  key_driver: string; // 핵심 상승/하락 요인 키워드
}

export interface AnalyzedArticle {
  title: string;
  url: string;
  source: string;
  published_at: string;
  impact_score: number;
}

export interface Briefing {
  date: string;
  data_as_of?: string;   // 유가 데이터의 마지막 날짜
  summary: string;
  key_factors: BriefingKeyFactor[];
  risk_scenarios: RiskScenario[];
  price_outlook: string;
  confidence_note?: string;
  crude_assessments: CrudeDailyAssessment[]; // 유종별 시세 변동 평가
  has_news: boolean;
  analyzed_articles?: AnalyzedArticle[]; // 분석에 사용된 기사 목록
  generated_at: string;
}

// ──────────────────────────────────────────────
// Method B: 펀더멘탈 분석 모델 타입
// ──────────────────────────────────────────────

export interface FundamentalSignal {
  signal_id: string;     // "inventory" | "production" | "seasonal" | "mean_reversion" | "dollar"
  name: string;          // 한국어 표시명
  change: number | null; // 예상 변동률 (0.01 = 1%)
  confidence: number;    // 0.0 ~ 1.0
  weight: number;        // 최종 합산 시 가중치 비율
  detail: string;        // 근거 설명
}

export interface FundamentalCrudeForecast {
  crude_type: string;
  current_price: number;
  estimated_7d: number;
  estimated_7d_high: number;
  estimated_7d_low: number;
  total_change_pct: number;
  signals: FundamentalSignal[];
  confidence: number;
}

export interface FundamentalForecastResult {
  forecasts_by_crude: Record<string, FundamentalCrudeForecast>;
  method: string;
  generated_at: string;
}

// ──────────────────────────────────────────────
// 이중 방법론 비교 타입
// ──────────────────────────────────────────────

export interface DualForecastResult {
  method_a: ForecastResult;
  method_b: FundamentalForecastResult;
  consensus: boolean;
  data_as_of?: string;   // 유가 데이터의 마지막 날짜
  generated_at: string;
}

