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

export async function fetchAdminProduction(
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
  return apiFetch(`/api/admin/data/production?${params.toString()}`);
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

// --- Pipeline Statistics ---
export interface CategoryStat {
  category: string;
  count: number;
  avg_impact_score: number | null;
}

export interface RelevanceStat {
  relevance: string;
  count: number;
}

export interface DailyPipelineStat {
  date: string;
  collected: number;
  classified: number;
}

export interface SourceClassificationStat {
  data_source: string;
  total: number;
  classified: number;
  classification_rate: number;
}

export interface ClassificationStats {
  total: number;
  classified: number;
  unclassified: number;
  failed: number;
  classification_rate: number;
  category_distribution: CategoryStat[];
  relevance_distribution: RelevanceStat[];
  daily_pipeline: DailyPipelineStat[];
  source_classification: SourceClassificationStat[];
}

export interface PipelineQueueItem {
  id: string;
  title: string;
  published_at: string;
  is_classified: number;
  classification_error: string | null;
  retry_count: number;
}

export interface PipelineQAItem {
  id: string;
  title: string;
  published_at: string;
  classification_result: any;
}

export interface BriefingHistoryItem {
  date: string;
  has_news: boolean;
  key_factors_count: number;
  risk_scenarios_count: number;
  crude_assessments_count: number;
  generated_at: string;
  summary_length: number;
}

export interface BriefingStats {
  total_briefings: number;
  recent: BriefingHistoryItem[];
}

export async function fetchClassificationStats(): Promise<ClassificationStats> {
  return apiFetch('/api/admin/pipeline/classification-stats');
}

export async function fetchBriefingStats(): Promise<BriefingStats> {
  return apiFetch('/api/admin/pipeline/briefing-stats');
}

// --- Crawl Center (V2) ---

export interface CrawlHistoryItem {
  id: number;
  source: string;
  task_type: string;
  status: string;
  records_count: number;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
}

export interface SourceHealthItem {
  data_source: string;
  article_count: number;
  newest_article: string | null;
  last_crawled: string | null;
  total_runs: number | null;
  success_runs: number | null;
  error_runs: number | null;
  avg_duration_ms: number | null;
  last_log_at: string | null;
}

export interface IntegrityProblem {
  id: string;
  title: string | null;
  description: string | null;
  url: string;
  data_source: string;
  published_at: string | null;
  hold_status: number;
  issue_type: string;
}

export interface IntegrityReport {
  summary: {
    no_title: number;
    no_desc: number;
    no_url: number;
    no_date: number;
    cls_broken: number;
    held: number;
    manual_input: number;
    dup_urls: number;
  };
  problems: IntegrityProblem[];
}

export async function updateSchedulerConfig(intervalHours: number): Promise<SchedulerStatus> {
  return apiFetch(`/api/admin/scheduler/config?interval_hours=${intervalHours}`, { method: 'PUT' });
}

export async function triggerNewsCrawl(): Promise<{ status: string; message: string }> {
  return apiFetch('/api/admin/scheduler/trigger-news', { method: 'POST' });
}

export async function fetchCrawlHistory(limit: number = 50, date?: string): Promise<CrawlHistoryItem[]> {
  let url = `/api/admin/crawl/history?limit=${limit}`;
  if (date) url += `&date=${date}`;
  return apiFetch(url);
}

export async function fetchArticlesByDate(date: string): Promise<CrawlArticleDetail[]> {
  return apiFetch(`/api/admin/crawl/articles/by-date?date=${date}`);
}

export async function fetchSourceHealth(): Promise<SourceHealthItem[]> {
  return apiFetch('/api/admin/crawl/source-health');
}

export async function fetchIntegrityReport(): Promise<IntegrityReport> {
  return apiFetch('/api/admin/news/integrity');
}

export async function updateArticleHoldStatus(ids: string[], holdStatus: number): Promise<{ updated: number }> {
  return apiFetch('/api/admin/data/hold', {
    method: 'PUT',
    body: JSON.stringify({ article_ids: ids, hold_status: holdStatus }),
  });
}

// --- Pipeline Control ---
export async function fetchPipelineQueue(): Promise<PipelineQueueItem[]> {
  return apiFetch('/api/admin/pipeline/queue');
}

export async function fetchPipelineQA(): Promise<PipelineQAItem[]> {
  return apiFetch('/api/admin/pipeline/qa');
}

export async function retryPipelineItems(ids: string[]): Promise<{ message: string }> {
  return apiFetch('/api/admin/pipeline/retry', {
    method: 'POST',
    body: JSON.stringify({ article_ids: ids }),
  });
}

export async function overridePipelineClassification(id: string, category: string, impactScore: number): Promise<{ message: string }> {
  return apiFetch('/api/admin/pipeline/override', {
    method: 'PUT',
    body: JSON.stringify({ article_id: id, category: category, impact_score: impactScore }),
  });
}

export async function manualInsertArticle(data: Record<string, any>): Promise<{ status: string; id: string }> {
  return apiFetch('/api/admin/news/manual-insert', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function retryIntegrity(ids: string[]): Promise<{ status: string; message: string }> {
  return apiFetch('/api/admin/news/retry-integrity', {
    method: 'POST',
    body: JSON.stringify({ ids }),
  });
}

export interface CrawlArticleDetail {
  id: string;
  title: string;
  url: string;
  source_name: string;
  published_at: string;
  is_classified: number;
  issue_type: 'none' | 'no_desc' | 'cls_broken';
}

export async function fetchCrawlLogArticles(logId: number): Promise<CrawlArticleDetail[]> {
  return apiFetch(`/api/admin/crawl/history/${logId}/articles`);
}
