/**
 * Admin 전용 API 호출 함수
 * CRITICAL: 모든 외부 API 호출은 백엔드를 통해서만 수행
 */
import { apiFetch } from './api';
import type {
  OverviewResponse,
  CollectionLogsResponse,
  LogStatItem,
  RateLimitStatus,
  SchedulerStatus,
  ManualTriggerResponse,
  PaginatedDataResponse,
} from '../types/admin';

// --- Overview ---
export async function fetchAdminOverview(): Promise<OverviewResponse> {
  return apiFetch('/api/admin/overview');
}

// --- Collection Logs ---
export async function fetchCollectionLogs(
  source?: string,
  status?: string,
  limit = 50,
  offset = 0
): Promise<CollectionLogsResponse> {
  const params = new URLSearchParams();
  if (source) params.set('source', source);
  if (status) params.set('status', status);
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  return apiFetch(`/api/admin/logs?${params.toString()}`);
}

export async function fetchLogStats(): Promise<LogStatItem[]> {
  return apiFetch('/api/admin/logs/stats');
}

// --- Data Explorer ---
export async function fetchAdminPrices(
  startDate?: string,
  endDate?: string,
  limit = 50,
  offset = 0
): Promise<PaginatedDataResponse> {
  const params = new URLSearchParams();
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  return apiFetch(`/api/admin/data/prices?${params.toString()}`);
}

export async function fetchAdminMacro(
  startDate?: string,
  endDate?: string,
  limit = 50,
  offset = 0
): Promise<PaginatedDataResponse> {
  const params = new URLSearchParams();
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  return apiFetch(`/api/admin/data/macro?${params.toString()}`);
}

export async function fetchAdminNews(
  dataSource?: string,
  limit = 50,
  offset = 0
): Promise<PaginatedDataResponse> {
  const params = new URLSearchParams();
  if (dataSource) params.set('data_source', dataSource);
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  return apiFetch(`/api/admin/data/news?${params.toString()}`);
}

export async function fetchAdminInventory(
  startDate?: string,
  endDate?: string,
  limit = 50,
  offset = 0
): Promise<PaginatedDataResponse> {
  const params = new URLSearchParams();
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  return apiFetch(`/api/admin/data/inventory?${params.toString()}`);
}

// --- Rate Limits ---
export async function fetchRateLimits(): Promise<RateLimitStatus[]> {
  return apiFetch('/api/admin/rate-limits');
}

// --- Manual Trigger ---
export async function triggerCollection(source: string): Promise<ManualTriggerResponse> {
  return apiFetch('/api/admin/collect/trigger', {
    method: 'POST',
    body: JSON.stringify({ source }),
  });
}

// --- Scheduler ---
export async function fetchSchedulerStatus(): Promise<SchedulerStatus> {
  return apiFetch('/api/admin/scheduler/status');
}

export async function toggleScheduler(): Promise<SchedulerStatus> {
  return apiFetch('/api/admin/scheduler/toggle', { method: 'POST' });
}

// --- Crawl Control ---
export async function startCrawl(target: number, startYear?: number): Promise<{ status: string; message: string }> {
  const params = new URLSearchParams();
  params.set('target', String(target));
  if (startYear) params.set('start_year', String(startYear));
  return apiFetch(`/api/admin/crawl/start?${params.toString()}`, { method: 'POST' });
}

export async function stopCrawl(): Promise<{ status: string; message: string }> {
  return apiFetch('/api/admin/crawl/stop', { method: 'POST' });
}

export interface CrawlStatus {
  is_running: boolean;
  started_at: string | null;
  target: number;
  collected: number;
  current_year: number | null;
  recent_logs: string[];
}

export async function fetchCrawlStatus(): Promise<CrawlStatus> {
  return apiFetch('/api/admin/crawl/status');
}

export interface SourceStat {
  data_source: string;
  count: number;
  oldest_date: string | null;
  newest_date: string | null;
  source_count: number;
}

export interface YearlyStat {
  year: string;
  data_source: string;
  count: number;
}

export interface CrawlStats {
  total_count: number;
  by_source: SourceStat[];
  by_year: YearlyStat[];
}

export async function fetchCrawlStats(): Promise<CrawlStats> {
  return apiFetch('/api/admin/crawl/stats');
}
