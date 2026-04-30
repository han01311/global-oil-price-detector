/**
 * Admin 페이지용 TypeScript 타입 정의
 */

export interface TableStat {
  count: number;
  last_collected: string | null;
}

export interface OverviewResponse {
  oil_prices: TableStat;
  oil_inventory: TableStat;
  oil_production: TableStat;
  macro_indicators: TableStat;
  news_articles: TableStat;
  collection_logs: TableStat;
}

export interface CollectionLog {
  id: number;
  source: string;
  task_type: string;
  status: 'success' | 'error' | 'rate_limited' | 'skipped' | 'running';
  records_count: number;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
}

export interface CollectionLogsResponse {
  logs: CollectionLog[];
  total: number;
}

export interface LogStatItem {
  source: string;
  total_runs: number;
  success_count: number;
  error_count: number;
  rate_limited_count: number;
  last_run_at: string | null;
  total_records: number;
}

export interface RateLimitStatus {
  source: string;
  used: number;
  limit: number | null;
  remaining: number | null;
  last_request_at: string | null;
  min_interval_seconds: number;
}

export interface SchedulerStatus {
  is_running: boolean;
  interval_hours: number;
  jobs: SchedulerJob[];
  job_count: number;
}

export interface SchedulerJob {
  id: string;
  name: string;
  next_run: string | null;
}

export interface ManualTriggerResponse {
  status: string;
  message: string;
}

export interface PaginatedDataResponse {
  data: Record<string, unknown>[];
  total: number;
  limit: number;
  offset: number;
}
