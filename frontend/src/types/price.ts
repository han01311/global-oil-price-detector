export interface OilPrice {
  date: string; // YYYY-MM-DD
  dubai: number | null;
  wti: number | null;
  brent: number | null;
}

export interface PriceHistory {
  prices: OilPrice[];
  source: string;
  last_updated: string;
}

export interface MacroIndicator {
  date: string;
  fed_rate: number | null;
  dollar_index: number | null;
  cpi: number | null;
  industrial_prod: number | null;
  yield_spread: number | null;
}

export interface MacroHistory {
  indicators: MacroIndicator[];
  source: string;
  last_updated: string;
}
