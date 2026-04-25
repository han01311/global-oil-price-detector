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
