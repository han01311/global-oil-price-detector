import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  fetchAdminOverview,
  fetchCollectionLogs,
  fetchRateLimits,
  fetchSchedulerStatus,
  toggleScheduler,
  triggerCollection,
  fetchAdminPrices,
  fetchAdminMacro,
  fetchAdminNews,
  fetchAdminInventory,
  startCrawl,
  stopCrawl,
  fetchCrawlStatus,
  fetchCrawlStats,
} from '../../services/adminApi';
import type {
  OverviewResponse,
  CollectionLog,
  RateLimitStatus,
  SchedulerStatus,
  PaginatedDataResponse,
} from '../../types/admin';
import type { CrawlStatus, CrawlStats } from '../../services/adminApi';
import './AdminPanel.css';

type TabId = 'overview' | 'logs' | 'data' | 'trigger' | 'crawl';
type DataTab = 'prices' | 'macro' | 'news' | 'inventory';

// ═══════════════════════════════════════════════
// Helper Components
// ═══════════════════════════════════════════════

const SourceTag: React.FC<{ source: string }> = ({ source }) => (
  <span className={`source-tag ${source}`}>{source.toUpperCase()}</span>
);

const StatusBadge: React.FC<{ status: string }> = ({ status }) => (
  <span className={`status-badge ${status}`}>
    {status === 'success' ? '✓' : status === 'error' ? '✕' : status === 'rate_limited' ? '⏱' : '●'} {status}
  </span>
);

const formatDate = (iso: string | null): string => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch {
    return iso;
  }
};

const formatNumber = (n: number): string =>
  n >= 1000 ? `${(n / 1000).toFixed(1)}K` : String(n);

// ═══════════════════════════════════════════════
// Overview Section
// ═══════════════════════════════════════════════

const OverviewSection: React.FC = () => {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [rateLimits, setRateLimits] = useState<RateLimitStatus[]>([]);
  const [scheduler, setScheduler] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [ov, rl, sc] = await Promise.all([
          fetchAdminOverview(),
          fetchRateLimits(),
          fetchSchedulerStatus(),
        ]);
        setOverview(ov);
        setRateLimits(rl);
        setScheduler(sc);
      } catch (e) {
        console.error('Failed to load overview:', e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleToggleScheduler = async () => {
    try {
      const result = await toggleScheduler();
      setScheduler(result);
    } catch (e) {
      console.error('Failed to toggle scheduler:', e);
    }
  };

  if (loading) {
    return (
      <div className="overview-grid">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="overview-card">
            <div className="admin-skeleton" style={{ width: '60%', height: 14, marginBottom: 10 }} />
            <div className="admin-skeleton" style={{ width: '40%', height: 32 }} />
          </div>
        ))}
      </div>
    );
  }

  const tableCards = overview ? [
    { key: 'oil_prices', label: 'Oil Prices', stat: overview.oil_prices },
    { key: 'oil_inventory', label: 'Inventory', stat: overview.oil_inventory },
    { key: 'oil_production', label: 'Production', stat: overview.oil_production },
    { key: 'macro_indicators', label: 'Macro', stat: overview.macro_indicators },
    { key: 'news_articles', label: 'News', stat: overview.news_articles },
    { key: 'collection_logs', label: 'Logs', stat: overview.collection_logs },
  ] : [];

  return (
    <>
      {/* Scheduler Bar */}
      {scheduler && (
        <div className="scheduler-bar">
          <div className="scheduler-info">
            <div className={`scheduler-status-dot ${scheduler.is_running ? 'running' : 'stopped'}`} />
            <span className="scheduler-label">
              Scheduler: <strong>{scheduler.is_running ? 'Running' : 'Stopped'}</strong>
              {scheduler.is_running && ` · ${scheduler.interval_hours}h interval · ${scheduler.jobs.length} jobs`}
            </span>
          </div>
          <button className="scheduler-toggle-btn" onClick={handleToggleScheduler}>
            {scheduler.is_running ? '⏸ Pause' : '▶ Start'}
          </button>
        </div>
      )}

      {/* DB Table Stats */}
      <h3 className="section-title">Database Overview</h3>
      <div className="overview-grid">
        {tableCards.map(({ key, label, stat }) => (
          <div className="overview-card" key={key}>
            <div className="overview-card-label">{label}</div>
            <div className="overview-card-value">{formatNumber(stat.count)}</div>
            <div className="overview-card-meta">
              {stat.last_collected ? `Last: ${formatDate(stat.last_collected)}` : 'No data yet'}
            </div>
          </div>
        ))}
      </div>

      {/* Rate Limit Gauges */}
      <h3 className="section-title">Rate Limit Usage (Today)</h3>
      <div className="rate-limit-grid">
        {rateLimits.map((rl) => {
          const pct = rl.limit ? Math.min((rl.used / rl.limit) * 100, 100) : 100;
          const level = rl.limit === null ? 'unlimited' : pct > 80 ? 'danger' : pct > 50 ? 'warning' : 'safe';
          return (
            <div className="rate-limit-card" key={rl.source}>
              <div className="rate-limit-header">
                <span className="rate-limit-source">{rl.source}</span>
                <span className="rate-limit-counter">
                  {rl.limit ? `${rl.used}/${rl.limit}` : `${rl.used} calls`}
                </span>
              </div>
              <div className="rate-limit-bar">
                <div
                  className={`rate-limit-fill ${level}`}
                  style={{ width: `${rl.limit ? pct : 100}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
};

// ═══════════════════════════════════════════════
// Collection Logs Section
// ═══════════════════════════════════════════════

const LogsSection: React.FC = () => {
  const [logs, setLogs] = useState<CollectionLog[]>([]);
  const [total, setTotal] = useState(0);
  const [sourceFilter, setSourceFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const limit = 20;

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchCollectionLogs(
        sourceFilter || undefined,
        statusFilter || undefined,
        limit,
        offset
      );
      setLogs(res.logs);
      setTotal(res.total);
    } catch (e) {
      console.error('Failed to load logs:', e);
    } finally {
      setLoading(false);
    }
  }, [sourceFilter, statusFilter, offset]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  return (
    <>
      <div className="filters-bar">
        <select className="filter-select" value={sourceFilter} onChange={(e) => { setSourceFilter(e.target.value); setOffset(0); }}>
          <option value="">All Sources</option>
          <option value="opinet">Opinet</option>
          <option value="eia">EIA</option>
          <option value="fred">FRED</option>
          <option value="news">News</option>
        </select>
        <select className="filter-select" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setOffset(0); }}>
          <option value="">All Status</option>
          <option value="success">Success</option>
          <option value="error">Error</option>
          <option value="rate_limited">Rate Limited</option>
        </select>
      </div>

      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Source</th>
              <th>Type</th>
              <th>Status</th>
              <th>Records</th>
              <th>Duration</th>
              <th>Completed</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              [...Array(5)].map((_, i) => (
                <tr key={i}>
                  {[...Array(7)].map((__, j) => (
                    <td key={j}><div className="admin-skeleton" style={{ height: 14, width: '80%' }} /></td>
                  ))}
                </tr>
              ))
            ) : logs.length === 0 ? (
              <tr>
                <td colSpan={7}>
                  <div className="admin-empty">
                    <div className="admin-empty-icon">📋</div>
                    <div className="admin-empty-text">No collection logs yet</div>
                  </div>
                </td>
              </tr>
            ) : (
              logs.map((log) => (
                <tr key={log.id}>
                  <td><SourceTag source={log.source} /></td>
                  <td>{log.task_type}</td>
                  <td><StatusBadge status={log.status} /></td>
                  <td>{log.records_count}</td>
                  <td>{log.duration_ms ? `${(log.duration_ms / 1000).toFixed(1)}s` : '—'}</td>
                  <td>{formatDate(log.completed_at)}</td>
                  <td title={log.error_message || ''}>{log.error_message ? log.error_message.slice(0, 60) + '…' : '—'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        <div className="pagination-bar">
          <span className="pagination-info">
            Showing {offset + 1}–{Math.min(offset + limit, total)} of {total}
          </span>
          <div className="pagination-buttons">
            <button className="pagination-btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
              ← Prev
            </button>
            <button className="pagination-btn" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}>
              Next →
            </button>
          </div>
        </div>
      </div>
    </>
  );
};

// ═══════════════════════════════════════════════
// Data Explorer Section
// ═══════════════════════════════════════════════

const DataExplorerSection: React.FC = () => {
  const [activeTab, setActiveTab] = useState<DataTab>('prices');
  const [data, setData] = useState<PaginatedDataResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const limit = 30;

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      let res: PaginatedDataResponse;
      switch (activeTab) {
        case 'prices':
          res = await fetchAdminPrices(undefined, undefined, limit, offset);
          break;
        case 'macro':
          res = await fetchAdminMacro(undefined, undefined, limit, offset);
          break;
        case 'news':
          res = await fetchAdminNews(undefined, limit, offset);
          break;
        case 'inventory':
          res = await fetchAdminInventory(undefined, undefined, limit, offset);
          break;
      }
      setData(res);
    } catch (e) {
      console.error('Failed to load data:', e);
    } finally {
      setLoading(false);
    }
  }, [activeTab, offset]);

  useEffect(() => {
    setOffset(0);
  }, [activeTab]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  let columns = data?.data?.[0] ? Object.keys(data.data[0]) : [];
  
  if (activeTab === 'prices' && columns.length > 0) {
    const preferredOrder = ['id', 'date', 'dubai', 'brent', 'wti', 'source', 'collected_at'];
    columns = columns.sort((a, b) => {
      const idxA = preferredOrder.indexOf(a);
      const idxB = preferredOrder.indexOf(b);
      if (idxA === -1 && idxB === -1) return 0;
      if (idxA === -1) return 1;
      if (idxB === -1) return -1;
      return idxA - idxB;
    });
  }

  return (
    <>
      <div className="data-tabs">
        {(['prices', 'macro', 'news', 'inventory'] as DataTab[]).map((tab) => (
          <button
            key={tab}
            className={`data-tab ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab === 'prices' ? '📈 Prices' : tab === 'macro' ? '🏛 Macro' : tab === 'news' ? '📰 News' : '🛢 Inventory'}
          </button>
        ))}
      </div>

      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              [...Array(5)].map((_, i) => (
                <tr key={i}>
                  {[...Array(Math.max(columns.length, 4))].map((__, j) => (
                    <td key={j}><div className="admin-skeleton" style={{ height: 14, width: '80%' }} /></td>
                  ))}
                </tr>
              ))
            ) : !data?.data?.length ? (
              <tr>
                <td colSpan={columns.length || 4}>
                  <div className="admin-empty">
                    <div className="admin-empty-icon">🗃</div>
                    <div className="admin-empty-text">No {activeTab} data collected yet</div>
                  </div>
                </td>
              </tr>
            ) : (
              data.data.map((row, i) => (
                <tr key={i}>
                  {columns.map((col) => (
                    <td key={col} title={String(row[col] ?? '')}>
                      {typeof row[col] === 'number'
                        ? (row[col] as number).toFixed?.(2) ?? row[col]
                        : String(row[col] ?? '—')}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
        {data && (
          <div className="pagination-bar">
            <span className="pagination-info">
              Showing {offset + 1}–{Math.min(offset + limit, data.total)} of {data.total}
            </span>
            <div className="pagination-buttons">
              <button className="pagination-btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
                ← Prev
              </button>
              <button className="pagination-btn" disabled={offset + limit >= data.total} onClick={() => setOffset(offset + limit)}>
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
};

// ═══════════════════════════════════════════════
// Manual Trigger Section
// ═══════════════════════════════════════════════

const TriggerSection: React.FC = () => {
  const [triggering, setTriggering] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, { status: string; message: string }>>({});

  const triggers = [
    { id: 'opinet_prices', label: 'Opinet Prices', desc: 'Dubai / Brent / WTI 현물가' },
    { id: 'eia_inventory', label: 'EIA Inventory', desc: '미국 원유 재고' },
    { id: 'eia_production', label: 'EIA Production', desc: '미국 원유 생산량' },
    { id: 'fred_macro', label: 'FRED Macro', desc: '금리, 달러 인덱스' },
    { id: 'news', label: 'All News', desc: 'NYT + Guardian' },
  ];

  const handleTrigger = async (source: string) => {
    setTriggering(source);
    try {
      const result = await triggerCollection(source);
      setResults((prev) => ({ ...prev, [source]: result }));
    } catch (e) {
      setResults((prev) => ({ ...prev, [source]: { status: 'error', message: String(e) } }));
    } finally {
      setTriggering(null);
    }
  };

  return (
    <div className="trigger-grid">
      {triggers.map(({ id, label, desc }) => (
        <div className="trigger-card" key={id}>
          <div className="trigger-card-title">{label}</div>
          <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.35)', textAlign: 'center' }}>{desc}</div>
          <button
            className={`trigger-btn ${triggering === id ? 'loading' : ''}`}
            disabled={triggering !== null}
            onClick={() => handleTrigger(id)}
          >
            {triggering === id ? 'Collecting...' : '⚡ Trigger'}
          </button>
          {results[id] && (
            <StatusBadge status={results[id].status} />
          )}
        </div>
      ))}
    </div>
  );
};

// ═══════════════════════════════════════════════
// Crawl Center Section
// ═══════════════════════════════════════════════

const CrawlCenterSection: React.FC = () => {
  const [status, setStatus] = useState<CrawlStatus | null>(null);
  const [stats, setStats] = useState<CrawlStats | null>(null);
  const [target, setTarget] = useState(2000);
  const [startYear, setStartYear] = useState(2000);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [message, setMessage] = useState('');
  const logEndRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const [s, st] = await Promise.all([fetchCrawlStatus(), fetchCrawlStats()]);
      setStatus(s);
      setStats(st);
    } catch (e) {
      console.error('Failed to load crawl data:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // 크롤링 중이면 2초마다 상태 폴링
  useEffect(() => {
    if (status?.is_running) {
      pollRef.current = setInterval(async () => {
        try {
          const [s, st] = await Promise.all([fetchCrawlStatus(), fetchCrawlStats()]);
          setStatus(s);
          setStats(st);
        } catch { /* silent */ }
      }, 2000);
    } else {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [status?.is_running]);

  // 로그 자동 스크롤
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [status?.recent_logs]);

  const handleStart = async () => {
    setActionLoading(true);
    setMessage('');
    try {
      const result = await startCrawl(target, startYear);
      setMessage(result.message);
      await loadAll();
    } catch (e) {
      setMessage(`오류: ${e}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleStop = async () => {
    setActionLoading(true);
    setMessage('');
    try {
      const result = await stopCrawl();
      setMessage(result.message);
      await loadAll();
    } catch (e) {
      setMessage(`오류: ${e}`);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="overview-grid">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="overview-card">
            <div className="admin-skeleton" style={{ width: '60%', height: 14, marginBottom: 10 }} />
            <div className="admin-skeleton" style={{ width: '40%', height: 32 }} />
          </div>
        ))}
      </div>
    );
  }

  const progressPct = status?.target ? Math.min((status.collected / status.target) * 100, 100) : 0;

  // 연도별 데이터를 바 차트용으로 가공
  const yearlyGroups: Record<string, Record<string, number>> = {};
  stats?.by_year?.forEach(({ year, data_source, count }) => {
    if (!yearlyGroups[year]) yearlyGroups[year] = {};
    yearlyGroups[year][data_source] = count;
  });
  const maxYearlyCount = Math.max(1, ...Object.values(yearlyGroups).map(g => Object.values(g).reduce((a, b) => a + b, 0)));

  return (
    <>
      {/* 크롤링 제어판 */}
      <div className="crawl-control-panel">
        <div className="crawl-control-header">
          <div className="crawl-status-indicator">
            <div className={`scheduler-status-dot ${status?.is_running ? 'running' : 'stopped'}`} />
            <span className="crawl-status-text">
              {status?.is_running ? `크롤링 진행 중 — ${status.current_year}년 수집 중` : '대기 중'}
            </span>
          </div>
          {message && <span className="crawl-message">{message}</span>}
        </div>

        <div className="crawl-controls">
          <div className="crawl-input-group">
            <label>목표 건수</label>
            <input
              type="number"
              className="filter-input"
              value={target}
              onChange={(e) => setTarget(Number(e.target.value))}
              disabled={status?.is_running}
              min={100}
              max={10000}
              step={100}
            />
          </div>
          <div className="crawl-input-group">
            <label>시작 연도</label>
            <input
              type="number"
              className="filter-input"
              value={startYear}
              onChange={(e) => setStartYear(Number(e.target.value))}
              disabled={status?.is_running}
              min={2000}
              max={2026}
            />
          </div>
          <div className="crawl-buttons">
            {status?.is_running ? (
              <button className="crawl-stop-btn" onClick={handleStop} disabled={actionLoading}>
                ⏹ 크롤링 중지
              </button>
            ) : (
              <button className="crawl-start-btn" onClick={handleStart} disabled={actionLoading}>
                🚀 크롤링 시작
              </button>
            )}
          </div>
        </div>

        {/* 진행률 바 */}
        {(status?.is_running || status?.collected! > 0) && (
          <div className="crawl-progress">
            <div className="crawl-progress-header">
              <span>{status?.collected?.toLocaleString()} / {status?.target?.toLocaleString()} 건</span>
              <span>{progressPct.toFixed(1)}%</span>
            </div>
            <div className="rate-limit-bar" style={{ height: 8 }}>
              <div
                className="rate-limit-fill safe"
                style={{ width: `${progressPct}%`, transition: 'width 0.5s ease' }}
              />
            </div>
          </div>
        )}
      </div>

      {/* 소스별 통계 카드 */}
      <h3 className="section-title">소스별 수집 현황</h3>
      <div className="overview-grid">
        <div className="overview-card">
          <div className="overview-card-label">TOTAL ARTICLES</div>
          <div className="overview-card-value">{stats?.total_count?.toLocaleString() ?? 0}</div>
          <div className="overview-card-meta">전체 수집된 뉴스 기사</div>
        </div>
        {stats?.by_source?.map((s) => (
          <div className="overview-card" key={s.data_source}>
            <div className="overview-card-label">
              <SourceTag source={s.data_source} />
            </div>
            <div className="overview-card-value">{s.count.toLocaleString()}</div>
            <div className="overview-card-meta">
              {s.oldest_date?.slice(0, 10)} ~ {s.newest_date?.slice(0, 10)}
              {' · '}{s.source_count} sources
            </div>
          </div>
        ))}
      </div>

      {/* 연도별 분포 바 차트 */}
      <h3 className="section-title">연도별 수집 분포</h3>
      <div className="crawl-yearly-chart">
        {Object.entries(yearlyGroups).map(([year, sources]) => {
          const total = Object.values(sources).reduce((a, b) => a + b, 0);
          return (
            <div className="crawl-year-row" key={year}>
              <span className="crawl-year-label">{year}</span>
              <div className="crawl-year-bar-container">
                {Object.entries(sources).map(([src, cnt]) => (
                  <div
                    key={src}
                    className={`crawl-year-bar-segment source-${src}`}
                    style={{ width: `${(cnt / maxYearlyCount) * 100}%` }}
                    title={`${src}: ${cnt}건`}
                  />
                ))}
              </div>
              <span className="crawl-year-count">{total}</span>
            </div>
          );
        })}
        {Object.keys(yearlyGroups).length === 0 && (
          <div className="admin-empty">
            <div className="admin-empty-icon">📊</div>
            <div className="admin-empty-text">아직 수집된 데이터가 없습니다</div>
          </div>
        )}
      </div>

      {/* 실시간 로그 */}
      {status?.recent_logs && status.recent_logs.length > 0 && (
        <>
          <h3 className="section-title">실시간 로그</h3>
          <div className="crawl-log-panel">
            {status.recent_logs.map((line, i) => (
              <div key={i} className="crawl-log-line">{line}</div>
            ))}
            <div ref={logEndRef} />
          </div>
        </>
      )}
    </>
  );
};

// ═══════════════════════════════════════════════
// Main Admin Panel
// ═══════════════════════════════════════════════

export const AdminPanel: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>('overview');

  const tabs: { id: TabId; label: string; icon: string }[] = [
    { id: 'overview', label: 'Overview', icon: '📊' },
    { id: 'crawl', label: 'Crawl Center', icon: '🕷' },
    { id: 'logs', label: 'Collection Logs', icon: '📋' },
    { id: 'data', label: 'Data Explorer', icon: '🗃' },
    { id: 'trigger', label: 'Manual Trigger', icon: '⚡' },
  ];

  return (
    <div className="admin-container">
      <div className="admin-header">
        <div className="admin-header-left">
          <h1>Petro-AX Admin</h1>
        </div>
        <Link to="/" className="admin-back-link">
          ← Dashboard
        </Link>
      </div>

      <div className="admin-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`admin-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && <OverviewSection />}
      {activeTab === 'crawl' && <CrawlCenterSection />}
      {activeTab === 'logs' && <LogsSection />}
      {activeTab === 'data' && <DataExplorerSection />}
      {activeTab === 'trigger' && <TriggerSection />}
    </div>
  );
};
