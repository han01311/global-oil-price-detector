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
  fetchClassificationStats,
  fetchBriefingStats,
  updateSchedulerConfig,
  triggerNewsCrawl,
  fetchCrawlHistory,
  fetchSourceHealth,
  fetchIntegrityReport,
  holdArticles,
  retryIntegrity,
  fetchCrawlLogArticles,
  fetchArticlesByDate,
} from '../../services/adminApi';
import type {
  OverviewResponse,
  CollectionLog,
  RateLimitStatus,
  SchedulerStatus,
  PaginatedDataResponse,
} from '../../types/admin';
import type {
  CrawlStatus, CrawlStats, ClassificationStats, BriefingStats,
  CrawlHistoryItem, SourceHealthItem, IntegrityReport, CrawlArticleDetail
} from '../../services/adminApi';
import './AdminPanel.css';

type TabId = 'overview' | 'logs' | 'data' | 'trigger' | 'crawl' | 'pipeline';
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

const getTimeUntil = (iso: string | null, nowMs: number): string => {
  if (!iso) return '';
  const diffMs = new Date(iso).getTime() - nowMs;
  if (diffMs <= 0) return '곧 실행됨';
  const hours = Math.floor(diffMs / (1000 * 60 * 60));
  const mins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
  const secs = Math.floor((diffMs % (1000 * 60)) / 1000);
  if (hours > 0) return `(약 ${hours}시간 ${mins}분 후)`;
  if (mins > 0) return `(약 ${mins}분 ${secs}초 후)`;
  return `(약 ${secs}초 후)`;
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
  const [subTab, setSubTab] = useState<'auto' | 'manual'>('auto');
  
  // Auto Crawl
  const [scheduler, setScheduler] = useState<SchedulerStatus | null>(null);
  const [intervalHours, setIntervalHours] = useState(6);
  const [currentTime, setCurrentTime] = useState(Date.now());
  
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  
  // Manual Crawl
  const [status, setStatus] = useState<CrawlStatus | null>(null);
  const [stats, setStats] = useState<CrawlStats | null>(null);
  const [target, setTarget] = useState(2000);
  const [startYear, setStartYear] = useState(2000);
  
  // History & Health
  const [history, setHistory] = useState<CrawlHistoryItem[]>([]);
  const [health, setHealth] = useState<SourceHealthItem[]>([]);
  
  // Integrity
  const [integrity, setIntegrity] = useState<IntegrityReport | null>(null);
  const [integrityTab, setIntegrityTab] = useState<'no_field' | 'cls_broken'>('no_field');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [message, setMessage] = useState('');
  
  // Log Detail Modal
  const [isLogModalOpen, setIsLogModalOpen] = useState(false);
  const [selectedLogId, setSelectedLogId] = useState<number | null>(null);
  const [logArticles, setLogArticles] = useState<CrawlArticleDetail[]>([]);
  const [logModalLoading, setLogModalLoading] = useState(false);
  
  // Date Filter
  const [historyDateFilter, setHistoryDateFilter] = useState('');
  const [selectedDateForModal, setSelectedDateForModal] = useState<string | null>(null);
  
  const logEndRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const [sc, s, st, h, hl, ig] = await Promise.all([
        fetchSchedulerStatus(),
        fetchCrawlStatus(),
        fetchCrawlStats(),
        fetchCrawlHistory(20, historyDateFilter || undefined),
        fetchSourceHealth(),
        fetchIntegrityReport()
      ]);
      setScheduler(sc);
      setIntervalHours(sc.interval_hours || 6);
      setStatus(s);
      setStats(st);
      setHistory(h);
      setHealth(hl);
      setIntegrity(ig);
    } catch (e) {
      console.error('Failed to load crawl data:', e);
    } finally {
      setLoading(false);
    }
  }, [historyDateFilter]);

  useEffect(() => { loadAll(); }, [loadAll]);

  // Polling for manual crawl and history
  useEffect(() => {
    const hasRunningManual = status?.is_running;
    const hasRunningHistory = history.some(h => h.status === 'running');
    
    if (hasRunningManual || hasRunningHistory) {
      pollRef.current = setInterval(async () => {
        try {
          if (hasRunningManual) {
            const [s, st] = await Promise.all([fetchCrawlStatus(), fetchCrawlStats()]);
            setStatus(s);
            setStats(st);
          }
          if (hasRunningHistory) {
            const h = await fetchCrawlHistory(20, historyDateFilter || undefined);
            setHistory(h);
          }
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
  }, [status?.is_running, history]);

  useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [status?.recent_logs]);

  const handleToggleScheduler = async () => {
    setActionLoading(true);
    try {
      const sc = await toggleScheduler();
      setScheduler(sc);
      setMessage(sc.is_running ? "스케줄러가 시작되었습니다." : "스케줄러가 정지되었습니다.");
    } catch (e) {
      setMessage(String(e));
    } finally {
      setActionLoading(false);
    }
  };

  const handleUpdateConfig = async () => {
    try {
      await updateSchedulerConfig(intervalHours);
      setMessage(`스케줄 간격이 ${intervalHours}시간으로 변경되었습니다.`);
      loadAll();
    } catch (e) { setMessage(String(e)); }
  };

  const handleTriggerNews = async () => {
    setActionLoading(true);
    try {
      const res = await triggerNewsCrawl();
      setMessage(res.message);
      // 백그라운드 태스크가 시작되고 로그가 생성될 시간을 약간 부여한 후 갱신
      setTimeout(() => {
        loadAll();
      }, 1000);
    } catch (e) { setMessage(String(e)); }
    setActionLoading(false);
  };

  const handleLogClick = async (log: CrawlHistoryItem) => {
    // 뉴스 크롤링 로그이면서 상태가 success/error일 때만 오픈
    if (log.source !== 'news' || log.status === 'running') return;
    setSelectedLogId(log.id);
    setSelectedDateForModal(null);
    setIsLogModalOpen(true);
    setLogModalLoading(true);
    try {
      const articles = await fetchCrawlLogArticles(log.id);
      setLogArticles(articles);
    } catch (e) {
      console.error(e);
    } finally {
      setLogModalLoading(false);
    }
  };

  const handleViewDateArticles = async () => {
    if (!historyDateFilter) return;
    setSelectedLogId(null);
    setSelectedDateForModal(historyDateFilter);
    setIsLogModalOpen(true);
    setLogModalLoading(true);
    try {
      const articles = await fetchArticlesByDate(historyDateFilter);
      setLogArticles(articles);
    } catch (e) {
      console.error(e);
    } finally {
      setLogModalLoading(false);
    }
  };

  const handleStart = async () => {
    setActionLoading(true);
    setMessage('');
    try {
      const result = await startCrawl(target, startYear);
      setMessage(result.message);
      await loadAll();
    } catch (e) { setMessage(`오류: ${e}`); }
    setActionLoading(false);
  };

  const handleStop = async () => {
    setActionLoading(true);
    setMessage('');
    try {
      const result = await stopCrawl();
      setMessage(result.message);
      await loadAll();
    } catch (e) { setMessage(`오류: ${e}`); }
    setActionLoading(false);
  };

  const handleHold = async (ids: string[], holdStatus: number) => {
    if (ids.length === 0) return;
    try {
      await holdArticles(ids, holdStatus);
      setSelectedIds(new Set());
      loadAll();
    } catch (e) { console.error(e); }
  };

  const handleRetryIntegrity = async (ids: string[]) => {
    if (ids.length === 0) return;
    try {
      await retryIntegrity(ids);
      setSelectedIds(new Set());
      loadAll();
    } catch (e) { console.error(e); }
  };

  const toggleSelection = (id: string) => {
    const newSel = new Set(selectedIds);
    if (newSel.has(id)) newSel.delete(id);
    else newSel.add(id);
    setSelectedIds(newSel);
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
  
  const yearlyGroups: Record<string, Record<string, number>> = {};
  stats?.by_year?.forEach(({ year, data_source, count }) => {
    if (!yearlyGroups[year]) yearlyGroups[year] = {};
    yearlyGroups[year][data_source] = count;
  });
  const maxYearlyCount = Math.max(1, ...Object.values(yearlyGroups).map(g => Object.values(g).reduce((a, b) => a + b, 0)));

  return (
    <div className="crawl-center-wrapper">
      <div className="crawl-subtabs">
        <button className={`crawl-subtab ${subTab === 'auto' ? 'active' : ''}`} onClick={() => setSubTab('auto')}>
          🔄 자동 크롤링
        </button>
        <button className={`crawl-subtab ${subTab === 'manual' ? 'active' : ''}`} onClick={() => setSubTab('manual')}>
          🔧 수동 크롤링
        </button>
      </div>

      <div className="crawl-panel">
        {subTab === 'auto' ? (
          <div className="crawl-auto-section">
            <div className="crawl-control-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <div className="crawl-status-indicator">
                  <div className={`scheduler-status-dot ${scheduler?.is_running ? 'running' : 'stopped'}`} />
                  <span className="crawl-status-text">
                    {scheduler?.is_running ? (
                      <>
                        스케줄러 활성 — {scheduler?.jobs?.length || 0} Jobs
                        <span style={{ fontSize: 12, color: 'rgba(0, 212, 255, 0.8)', marginLeft: 8, fontWeight: 500 }}>
                          (실시간 모니터링 중... {new Date(currentTime).toLocaleTimeString('en-US', { hour12: false })})
                        </span>
                      </>
                    ) : '스케줄러 중지'}
                  </span>
                </div>
                <button 
                  className={`action-btn small ${scheduler?.is_running ? 'danger' : 'primary'}`}
                  onClick={handleToggleScheduler}
                  disabled={actionLoading}
                >
                  {scheduler?.is_running ? '정지' : '활성화'}
                </button>
              </div>
              {message && <span className="crawl-message">{message}</span>}
            </div>

            <div className="crawl-controls" style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'flex-end', 
              padding: '16px 20px', 
              background: 'rgba(255, 255, 255, 0.02)', 
              borderRadius: '8px', 
              border: '1px solid rgba(255, 255, 255, 0.05)', 
              marginBottom: '24px',
              marginTop: '16px'
            }}>
              <div className="crawl-input-group" style={{ margin: 0, gap: '10px' }}>
                <label style={{ fontSize: '13px', color: '#e4e8ef', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                  ⏳ 자동 수집 간격 설정
                </label>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', padding: '4px 12px' }}>
                    <input
                      type="number"
                      value={intervalHours}
                      onChange={(e) => setIntervalHours(Number(e.target.value))}
                      min={1} max={24}
                      style={{ width: '40px', background: 'transparent', border: 'none', color: '#fff', fontSize: '15px', fontWeight: 500, textAlign: 'center', outline: 'none' }}
                    />
                    <span style={{ color: 'rgba(255, 255, 255, 0.5)', fontSize: '13px', marginLeft: '4px' }}>시간마다</span>
                  </div>
                  <button className="action-btn small primary" onClick={handleUpdateConfig} style={{ padding: '6px 16px' }}>적용</button>
                </div>
              </div>
              <div className="crawl-buttons" style={{ margin: 0, padding: 0 }}>
                <button className="action-btn secondary" onClick={handleTriggerNews} disabled={actionLoading} style={{ padding: '8px 20px' }}>
                  🚀 수동 수집 (지금 1회 실행)
                </button>
              </div>
            </div>

            <h3 className="section-title">⏳ 자동 수집 대기열 (다음 실행 예약)</h3>
            <div className="admin-table-container">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>수집 항목 (Job)</th>
                    <th>현재 상태</th>
                    <th>다음 실행 예정 시각</th>
                  </tr>
                </thead>
                <tbody>
                  {scheduler?.jobs?.map(job => (
                    <tr key={job.id}>
                      <td><strong>{job.name}</strong></td>
                      <td>
                        {scheduler.is_running ? (
                           <span className="issue-badge" style={{ background: 'rgba(0, 212, 255, 0.1)', color: '#00D4FF', borderColor: 'rgba(0, 212, 255, 0.3)' }}>
                             <span className="scheduler-status-dot running" style={{ display: 'inline-block', width: 6, height: 6, marginRight: 6 }} />
                             대기 중 (예약됨)
                           </span>
                        ) : (
                           <span className="issue-badge" style={{ background: 'rgba(255, 77, 77, 0.1)', color: '#ff4d4d', borderColor: 'rgba(255, 77, 77, 0.3)' }}>스케줄러 중지</span>
                        )}
                      </td>
                      <td style={{ color: job.next_run ? '#fff' : '#ff4d4d' }}>
                        {job.next_run ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            <span>{formatDate(job.next_run)}</span>
                            <span style={{ fontSize: 11, color: 'rgba(255, 255, 255, 0.5)' }}>{getTimeUntil(job.next_run, currentTime)}</span>
                          </div>
                        ) : '예약 없음 (스케줄러 중지)'}
                      </td>
                    </tr>
                  ))}
                  {(!scheduler?.jobs || scheduler.jobs.length === 0) && (
                    <tr><td colSpan={3} className="admin-empty-text">등록된 Job이 없습니다.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="crawl-manual-section">
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
                  min={100} max={10000} step={100}
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
                  min={2000} max={2026}
                />
              </div>
              <div className="crawl-buttons" style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: '8px' }}>
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

            {(status?.is_running || status?.collected! > 0) && (
              <div className="crawl-progress" style={{ marginTop: '24px' }}>
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
                  <div className="admin-empty-text">아직 수집된 데이터가 없습니다</div>
                </div>
              )}
            </div>

            {status?.recent_logs && status.recent_logs.length > 0 && (
              <div className="crawl-log-panel" style={{ marginTop: '24px' }}>
                {status.recent_logs.map((line, i) => (
                  <div key={i} className="crawl-log-line">{line}</div>
                ))}
                <div ref={logEndRef} />
              </div>
            )}
          </div>
        )}
      </div>

      <div className="crawl-split-grid">
        <div className="crawl-grid-col">
          <h3 className="section-title">🏥 소스 건강도</h3>
          <div className="admin-table-container">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>소스</th>
                  <th>최신 기사</th>
                  <th>에러율</th>
                  <th>평균 응답</th>
                </tr>
              </thead>
              <tbody>
                {health.map(h => {
                  const errorRate = h.total_runs ? ((h.error_runs || 0) / h.total_runs) * 100 : 0;
                  const isStale = h.newest_article && (new Date().getTime() - new Date(h.newest_article).getTime() > 30 * 24 * 3600 * 1000);
                  const isInactive = !h.newest_article || (new Date().getTime() - new Date(h.newest_article).getTime() > 365 * 24 * 3600 * 1000);
                  
                  return (
                    <tr key={h.data_source}>
                      <td><SourceTag source={h.data_source} /></td>
                      <td style={{ color: isInactive ? '#ff4d4d' : isStale ? '#ffb84d' : '#fff' }}>
                        {h.newest_article?.slice(0, 10) || '—'} {isInactive ? '❌' : isStale ? '⚠️' : '✅'}
                      </td>
                      <td>{errorRate.toFixed(1)}%</td>
                      <td>{h.avg_duration_ms ? `${h.avg_duration_ms}ms` : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div className="crawl-grid-col">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 className="section-title" style={{ margin: 0 }}>📋 크롤링 이력</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div className="quick-filters">
                <button 
                  className={`filter-chip ${historyDateFilter === '' ? 'active' : ''}`}
                  onClick={() => setHistoryDateFilter('')}
                >
                  전체
                </button>
                <button 
                  className={`filter-chip ${historyDateFilter === new Date().toISOString().split('T')[0] ? 'active' : ''}`}
                  onClick={() => setHistoryDateFilter(new Date().toISOString().split('T')[0])}
                >
                  오늘
                </button>
                <button 
                  className={`filter-chip ${historyDateFilter === new Date(Date.now() - 86400000).toISOString().split('T')[0] ? 'active' : ''}`}
                  onClick={() => setHistoryDateFilter(new Date(Date.now() - 86400000).toISOString().split('T')[0])}
                >
                  어제
                </button>
              </div>
              <input 
                type="date" 
                value={historyDateFilter}
                onChange={e => setHistoryDateFilter(e.target.value)}
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  color: '#fff',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  fontFamily: 'Inter, sans-serif'
                }}
              />
              {historyDateFilter && (
                <button 
                  className="action-btn small primary" 
                  onClick={handleViewDateArticles}
                  disabled={logModalLoading}
                  style={{ whiteSpace: 'nowrap' }}
                >
                  ✨ 이 날짜 통합 보기
                </button>
              )}
            </div>
          </div>
          <div className="admin-table-container">
            <table className="admin-table crawl-history-table">
              <thead>
                <tr>
                  <th>시각</th>
                  <th>소스</th>
                  <th>상태</th>
                  <th>소요시간</th>
                  <th>신규 수집</th>
                  <th style={{ width: 80 }}></th>
                </tr>
              </thead>
              <tbody>
                {history.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="admin-empty-text" style={{ padding: '40px 0' }}>
                      해당 일자에 진행된 크롤링 작업이 없습니다.
                    </td>
                  </tr>
                ) : (
                  history.map(item => (
                    <tr 
                      key={item.id} 
                      onClick={() => handleLogClick(item)}
                      style={{ 
                        cursor: (item.source === 'news' && item.status !== 'running') ? 'pointer' : 'default',
                        backgroundColor: selectedLogId === item.id ? 'rgba(0, 212, 255, 0.1)' : undefined
                      }}
                      className={(item.source === 'news' && item.status !== 'running') ? 'clickable-row' : ''}
                    >
                      <td>{formatDate(item.completed_at || item.started_at).slice(6)}</td>
                      <td><SourceTag source={`${item.source}/${item.task_type}`} /></td>
                      <td><StatusBadge status={item.status} /></td>
                      <td>{item.duration_ms ? `${(item.duration_ms/1000).toFixed(1)}s` : '—'}</td>
                      <td style={{ fontWeight: 500, color: item.records_count > 0 ? '#00D4FF' : '#fff' }}>{item.records_count}</td>
                      <td style={{ textAlign: 'right' }}>
                        {(item.source === 'news' && item.status !== 'running') && (
                          <span className="row-action-indicator">상세 보기 ›</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {integrity && (
        <div className="crawl-integrity-panel">
          <h3 className="section-title">🔍 데이터 완결성 검증</h3>
          <div className="integrity-cards">
            <div className="integrity-card">
              <div className="integrity-card-value warning">{integrity.summary.no_desc}</div>
              <div className="integrity-card-label">필드 누락 (desc)</div>
            </div>
            <div className="integrity-card">
              <div className="integrity-card-value warning">{integrity.summary.cls_broken}</div>
              <div className="integrity-card-label">분류 이상</div>
            </div>
            <div className="integrity-card">
              <div className="integrity-card-value">0</div>
              <div className="integrity-card-label">중복 URL</div>
            </div>
            <div className="integrity-card">
              <div className="integrity-card-value info">{integrity.summary.held}</div>
              <div className="integrity-card-label">보류 기사</div>
            </div>
          </div>

          <div className="integrity-tabs">
            <button className={`integrity-tab ${integrityTab === 'no_field' ? 'active' : ''}`} onClick={() => setIntegrityTab('no_field')}>필드 누락</button>
            <button className={`integrity-tab ${integrityTab === 'cls_broken' ? 'active' : ''}`} onClick={() => setIntegrityTab('cls_broken')}>분류 이상</button>
          </div>

          <div className="admin-table-container">
            <table className="admin-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}><input type="checkbox" onChange={(e) => {
                    const toSelect = integrity.problems.filter(p => (integrityTab === 'no_field' ? p.issue_type === 'no_desc' : p.issue_type === 'cls_broken'));
                    if (e.target.checked) setSelectedIds(new Set(toSelect.map(p => p.id)));
                    else setSelectedIds(new Set());
                  }} /></th>
                  <th>Title</th>
                  <th>문제</th>
                  <th>소스</th>
                  <th>조치</th>
                </tr>
              </thead>
              <tbody>
                {integrity.problems
                  .filter(p => (integrityTab === 'no_field' ? p.issue_type === 'no_desc' : p.issue_type === 'cls_broken'))
                  .map(p => (
                  <tr key={p.id}>
                    <td>
                      <input type="checkbox" checked={selectedIds.has(p.id)} onChange={() => toggleSelection(p.id)} />
                    </td>
                    <td style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <a href={p.url} target="_blank" rel="noreferrer" style={{ color: '#fff', textDecoration: 'none' }}>
                        {p.title || '(제목 없음)'}
                      </a>
                    </td>
                    <td><span className={`issue-badge ${p.issue_type}`}>{p.issue_type}</span></td>
                    <td><SourceTag source={p.data_source} /></td>
                    <td>
                      <button className="action-btn small" onClick={() => handleRetryIntegrity([p.id])} style={{ marginRight: 8 }}>재수집</button>
                      <button className="action-btn small secondary" onClick={() => handleHold([p.id], 1)}>보류</button>
                    </td>
                  </tr>
                ))}
                {integrity.problems.filter(p => (integrityTab === 'no_field' ? p.issue_type === 'no_desc' : p.issue_type === 'cls_broken')).length === 0 && (
                  <tr><td colSpan={5} className="admin-empty-text">해당되는 문제가 없습니다.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          
          <div className="integrity-actions">
            <span className="selected-count">선택: {selectedIds.size}건</span>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button className="action-btn" onClick={() => handleRetryIntegrity(Array.from(selectedIds))} disabled={selectedIds.size === 0}>
                🔄 선택 항목 재수집
              </button>
              <button className="action-btn secondary" onClick={() => handleHold(Array.from(selectedIds), 1)} disabled={selectedIds.size === 0}>
                ⏸ 선택 항목 보류
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Log Detail Modal */}
      {isLogModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsLogModalOpen(false)}>
          <div className="crawl-detail-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>크롤링 상세 내역 ({selectedDateForModal ? `${selectedDateForModal} 전체` : `작업 #${selectedLogId}`})</h3>
              <button className="close-btn" onClick={() => setIsLogModalOpen(false)}>✕</button>
            </div>
            <div className="modal-content">
              {logModalLoading ? (
                <div className="admin-skeleton" style={{ height: 200 }} />
              ) : logArticles.length === 0 ? (
                <div className="admin-empty-text">해당 {selectedDateForModal ? '일자' : '작업'}에서 신규 수집된 기사가 없습니다.</div>
              ) : (
                <>
                  <div className="modal-stats">
                    <div className="stat-badge">신규 수집: {logArticles.length}건</div>
                    <div className="stat-badge success">정상 분류: {logArticles.filter(a => a.is_classified === 1 && a.issue_type === 'none').length}건</div>
                    <div className="stat-badge warning">분류 에러: {logArticles.filter(a => a.issue_type === 'cls_broken').length}건</div>
                    <div className="stat-badge danger">필드 누락: {logArticles.filter(a => a.issue_type === 'no_desc').length}건</div>
                  </div>
                  <div className="admin-table-container" style={{ maxHeight: '400px', overflowY: 'auto' }}>
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>일시</th>
                          <th>소스</th>
                          <th>기사 제목</th>
                          <th>상태</th>
                        </tr>
                      </thead>
                      <tbody>
                        {logArticles.map(a => (
                          <tr key={a.id}>
                            <td>{formatDate(a.published_at || '').slice(6)}</td>
                            <td><SourceTag source={a.source_name || a.url} /></td>
                            <td style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              <a href={a.url} target="_blank" rel="noreferrer" style={{ color: '#fff', textDecoration: 'none' }}>
                                {a.title}
                              </a>
                            </td>
                            <td>
                              {a.issue_type !== 'none' ? (
                                <span className={`issue-badge ${a.issue_type}`}>{a.issue_type}</span>
                              ) : (
                                <span className="issue-badge" style={{ background: 'rgba(0,255,0,0.1)', color: '#00ff00', borderColor: 'rgba(0,255,0,0.3)' }}>정상</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ═══════════════════════════════════════════════
// Pipeline Management Section (크롤링 & 학습 관리)
// ═══════════════════════════════════════════════

const CATEGORY_KR: Record<string, string> = {
  geopolitics: '지정학',
  supply: '공급',
  demand: '수요',
  macro: '거시경제',
  climate: '기후/ESG',
  speculation: '투기/심리',
  other: '기타',
};

const PipelineSection: React.FC = () => {
  const [clsStats, setClsStats] = useState<ClassificationStats | null>(null);
  const [briefingStats, setBriefingStats] = useState<BriefingStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [cls, br] = await Promise.all([
          fetchClassificationStats(),
          fetchBriefingStats(),
        ]);
        setClsStats(cls);
        setBriefingStats(br);
      } catch (e) {
        console.error('Failed to load pipeline stats:', e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

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

  if (!clsStats) return null;

  const relevantCount = clsStats.relevance_distribution.find(r => r.relevance === 'relevant')?.count || 0;
  const irrelevantCount = clsStats.relevance_distribution.find(r => r.relevance === 'irrelevant')?.count || 0;
  const relevantPct = clsStats.classified > 0 ? (relevantCount / clsStats.classified * 100).toFixed(1) : '0';
  const maxCatCount = Math.max(1, ...clsStats.category_distribution.map(c => c.count));
  const maxDailyCollected = Math.max(1, ...clsStats.daily_pipeline.map(d => d.collected));

  return (
    <>
      {/* KPI 카드 */}
      <h3 className="section-title">AI 분류 파이프라인 현황</h3>
      <div className="overview-grid">
        <div className="overview-card">
          <div className="overview-card-label">전체 기사</div>
          <div className="overview-card-value">{clsStats.total.toLocaleString()}</div>
          <div className="overview-card-meta">수집된 전체 뉴스 기사</div>
        </div>
        <div className="overview-card">
          <div className="overview-card-label">AI 분류 완료</div>
          <div className="overview-card-value" style={{ color: 'var(--color-success)' }}>
            {clsStats.classified.toLocaleString()}
          </div>
          <div className="overview-card-meta">
            분류율: {clsStats.classification_rate}%
          </div>
        </div>
        <div className="overview-card">
          <div className="overview-card-label">미분류</div>
          <div className="overview-card-value" style={{ color: clsStats.unclassified > 0 ? 'var(--color-warning)' : 'var(--color-text-muted)' }}>
            {clsStats.unclassified.toLocaleString()}
          </div>
          <div className="overview-card-meta">분류 대기 중인 기사</div>
        </div>
        <div className="overview-card">
          <div className="overview-card-label">유가 관련성</div>
          <div className="overview-card-value">{relevantPct}%</div>
          <div className="overview-card-meta">
            관련 {relevantCount.toLocaleString()} · 비관련 {irrelevantCount.toLocaleString()}
          </div>
        </div>
        <div className="overview-card">
          <div className="overview-card-label">생성된 브리핑</div>
          <div className="overview-card-value">{briefingStats?.total_briefings ?? 0}</div>
          <div className="overview-card-meta">일자별 AI Daily Briefing</div>
        </div>
        <div className="overview-card">
          <div className="overview-card-label">분류 카테고리</div>
          <div className="overview-card-value">{clsStats.category_distribution.length}</div>
          <div className="overview-card-meta">활성 분류 카테고리 수</div>
        </div>
      </div>

      {/* 분류율 진행바 */}
      <div className="pipeline-progress-section">
        <div className="pipeline-progress-header">
          <span>전체 분류 진행률</span>
          <span>{clsStats.classification_rate}%</span>
        </div>
        <div className="rate-limit-bar" style={{ height: 10 }}>
          <div
            className={`rate-limit-fill ${clsStats.classification_rate > 80 ? 'safe' : clsStats.classification_rate > 50 ? 'warning' : 'danger'}`}
            style={{ width: `${clsStats.classification_rate}%` }}
          />
        </div>
      </div>

      {/* 카테고리별 분포 바 차트 */}
      <h3 className="section-title">카테고리별 분류 분포</h3>
      <div className="pipeline-chart">
        {clsStats.category_distribution.map((cat) => {
          const label = CATEGORY_KR[cat.category] || cat.category || '미분류';
          const pct = (cat.count / maxCatCount * 100);
          return (
            <div className="pipeline-bar-row" key={cat.category}>
              <span className="pipeline-bar-label">
                <span className={`source-tag ${cat.category}`}>{label}</span>
              </span>
              <div className="pipeline-bar-container">
                <div
                  className={`pipeline-bar-fill source-${cat.category}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="pipeline-bar-count">
                {cat.count.toLocaleString()}
                {cat.avg_impact_score != null && (
                  <span className="pipeline-bar-meta"> · avg {cat.avg_impact_score > 0 ? '+' : ''}{cat.avg_impact_score}</span>
                )}
              </span>
            </div>
          );
        })}
        {clsStats.category_distribution.length === 0 && (
          <div className="admin-empty">
            <div className="admin-empty-icon">📊</div>
            <div className="admin-empty-text">분류된 데이터가 없습니다</div>
          </div>
        )}
      </div>

      {/* 소스별 분류율 */}
      <h3 className="section-title">소스별 분류율</h3>
      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Source</th>
              <th>전체</th>
              <th>분류완료</th>
              <th>분류율</th>
              <th>Progress</th>
            </tr>
          </thead>
          <tbody>
            {clsStats.source_classification.map((s) => (
              <tr key={s.data_source}>
                <td><SourceTag source={s.data_source || 'unknown'} /></td>
                <td>{s.total.toLocaleString()}</td>
                <td>{s.classified.toLocaleString()}</td>
                <td>{s.classification_rate}%</td>
                <td style={{ width: '30%' }}>
                  <div className="rate-limit-bar" style={{ height: 6 }}>
                    <div
                      className={`rate-limit-fill ${s.classification_rate > 80 ? 'safe' : s.classification_rate > 50 ? 'warning' : 'danger'}`}
                      style={{ width: `${s.classification_rate}%` }}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 일별 수집/분류 추이 */}
      <h3 className="section-title">일별 수집 · 분류 추이 (최근 30일)</h3>
      <div className="pipeline-daily-chart">
        {clsStats.daily_pipeline.length > 0 ? (
          <div className="pipeline-daily-bars">
            {clsStats.daily_pipeline.map((d) => (
              <div className="pipeline-daily-col" key={d.date} title={`${d.date}: 수집 ${d.collected} / 분류 ${d.classified}`}>
                <div className="pipeline-daily-bar-group">
                  <div
                    className="pipeline-daily-bar collected"
                    style={{ height: `${(d.collected / maxDailyCollected) * 100}%` }}
                  />
                  <div
                    className="pipeline-daily-bar classified"
                    style={{ height: `${(d.classified / maxDailyCollected) * 100}%` }}
                  />
                </div>
                <span className="pipeline-daily-label">{d.date.slice(5)}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="admin-empty">
            <div className="admin-empty-icon">📅</div>
            <div className="admin-empty-text">최근 30일 수집 데이터가 없습니다</div>
          </div>
        )}
        <div className="pipeline-daily-legend">
          <span><span className="legend-dot collected" /> 수집</span>
          <span><span className="legend-dot classified" /> AI 분류 완료</span>
        </div>
      </div>

      {/* 브리핑 생성 이력 */}
      {briefingStats && briefingStats.recent.length > 0 && (
        <>
          <h3 className="section-title">브리핑 생성 이력</h3>
          <div className="admin-table-wrapper">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>날짜</th>
                  <th>뉴스 기반</th>
                  <th>주요 요인</th>
                  <th>리스크</th>
                  <th>유종 평가</th>
                  <th>생성 시각</th>
                </tr>
              </thead>
              <tbody>
                {briefingStats.recent.map((b) => (
                  <tr key={b.date}>
                    <td>{b.date}</td>
                    <td><StatusBadge status={b.has_news ? 'success' : 'error'} /></td>
                    <td>{b.key_factors_count}</td>
                    <td>{b.risk_scenarios_count}</td>
                    <td>{b.crude_assessments_count}</td>
                    <td>{formatDate(b.generated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
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
  const [activeTab, setActiveTab] = useState<TabId>(() => {
    return (localStorage.getItem('adminActiveTab') as TabId) || 'overview';
  });

  useEffect(() => {
    localStorage.setItem('adminActiveTab', activeTab);
  }, [activeTab]);

  const tabs: { id: TabId; label: string; icon: string }[] = [
    { id: 'overview', label: 'Overview', icon: '📊' },
    { id: 'pipeline', label: 'Pipeline', icon: '🧠' },
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
      {activeTab === 'pipeline' && <PipelineSection />}
      {activeTab === 'crawl' && <CrawlCenterSection />}
      {activeTab === 'logs' && <LogsSection />}
      {activeTab === 'data' && <DataExplorerSection />}
      {activeTab === 'trigger' && <TriggerSection />}
    </div>
  );
};
