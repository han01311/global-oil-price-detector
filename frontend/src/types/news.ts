export interface NewsArticle {
  id: string;
  title: string;
  description: string | null;
  source: string | null;
  url: string;
  published_at: string; // ISO 8601
  content_snippet: string | null;
  data_source: string; // "newsapi" | "gdelt"
}

export interface CrudeImpact {
  direction: 'bullish' | 'bearish' | 'neutral';
  score: number; // -5 to 5
  rationale: string;
}

export interface ClassifiedArticle {
  article: NewsArticle;
  is_relevant: boolean;
  category: string;
  sub_categories: string[];
  impact_score: number; // -5 to 5
  impact_summary: string;
  confidence: number; // 0.0 to 1.0
  classified_at: string; // ISO 8601
  translated_title?: string; // Korean translated title
  impact_by_crude: Record<string, CrudeImpact>; // {"dubai": ..., "brent": ..., "wti": ...}
}

export interface SimilarEvent {
  title: string;
  translated_title?: string;
  summary: string;
  category: string;
  impact_score: number;
  date: string;
  url: string;
  wti_change_1d: number | null;
  wti_change_7d: number | null;
  wti_change_30d: number | null;
  dubai_change_1d: number | null;
  dubai_change_7d: number | null;
  dubai_change_30d: number | null;
  brent_change_1d: number | null;
  brent_change_7d: number | null;
  brent_change_30d: number | null;
  similarity: number; // 0.0 to 1.0
}

export interface FactorScore {
  category: string;
  avg_score: number;
  article_count: number;
  trend: 'bullish' | 'bearish' | 'neutral';
}

export interface FactorSummary {
  factors: FactorScore[];
  overall_sentiment: number; // -5 to 5
  updated_at: string;
}
