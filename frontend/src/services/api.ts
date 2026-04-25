import type { PriceHistory } from "../types/price";
import type { ClassifiedArticle, FactorSummary, SimilarEvent } from "../types/news";
import type { ForecastResult, Briefing } from "../types/forecast";
import type { OilPrice } from "../types/price";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * 백엔드 API 호출 래퍼
 * CRITICAL: 모든 외부 API 호출은 백엔드를 통해서만 수행
 */
export async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(`API Error: ${response.status} ${errorData.detail || response.statusText}`);
  }

  return response.json();
}

/**
 * 헬스체크 API
 */
export async function checkHealth(): Promise<{ status: string; version: string }> {
  return apiFetch("/api/health");
}

// --- Price APIs ---
export async function fetchPriceHistory(startDate: string, endDate: string): Promise<PriceHistory> {
  return apiFetch(`/api/prices/history?start_date=${startDate}&end_date=${endDate}`);
}

export async function fetchLatestPrice(): Promise<OilPrice> {
  return apiFetch("/api/prices/latest");
}

// --- News APIs ---
export async function fetchAndClassifyNews(): Promise<ClassifiedArticle[]> {
  // This endpoint fetches latest news and classifies them on the fly
  return apiFetch(`/api/news/classify?fetch_latest=true`, { method: 'POST' });
}

export async function fetchSimilarEvents(query: string, crudeType?: string): Promise<SimilarEvent[]> {
  let url = `/api/news/similar?query=${encodeURIComponent(query)}`;
  if (crudeType) {
    url += `&crude_type=${crudeType}`;
  }
  return apiFetch(url);
}

export async function fetchFactorSummary(): Promise<FactorSummary> {
  return apiFetch("/api/news/factors/summary");
}

// --- Forecast & Briefing APIs ---
export async function fetchForecastEstimate(): Promise<ForecastResult> {
  return apiFetch("/api/forecast/estimate");
}

export async function fetchTodayBriefing(): Promise<Briefing> {
  return apiFetch("/api/briefing/today");
}

export async function fetchBriefingHistory(days: number): Promise<Briefing[]> {
  return apiFetch(`/api/briefing/history?days=${days}`);
}

