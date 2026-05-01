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
  fetchAdminProduction,
  startCrawl,
  stopCrawl,
  fetchCrawlStatus,
  fetchCrawlStats,
  updateSchedulerConfig,
  triggerNewsCrawl,
  fetchCrawlHistory,
  fetchSourceHealth,
  fetchIntegrityReport,
  updateArticleHoldStatus,
  retryIntegrity,
  fetchCrawlLogArticles,
  fetchYearCoverage,
  searchCrawlArticles,
  deleteCrawlArticles,
  recrawlArticles,
} from '../../services/adminApi';
import type {
  OverviewResponse,
  CollectionLog,
  RateLimitStatus,
  SchedulerStatus,
  PaginatedDataResponse,
} from '../../types/admin';
import type {
  CrawlStatus, CrawlStats,
  CrawlHistoryItem, SourceHealthItem, IntegrityReport, CrawlArticleDetail,
  YearCoverageItem, CrawlSearchArticle,
} from '../../services/adminApi';
import './AdminPanel.css';

type TabId = 'overview' | 'logs' | 'data' | 'trigger' | 'crawl' | 'pipeline';
type DataTab = 'prices' | 'macro' | 'news' | 'inventory' | 'production';

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
        case 'production':
          res = await fetchAdminProduction(undefined, undefined, limit, offset);
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
  } else if (activeTab === 'news' && columns.length > 0) {
    const preferredOrder = ['id', 'data_source', 'title', 'description', 'url', 'published_at', 'collected_at', 'is_classified'];
    columns = columns.sort((a, b) => {
      const idxA = preferredOrder.indexOf(a);
      const idxB = preferredOrder.indexOf(b);
      if (idxA === -1 && idxB === -1) return 0;
      if (idxA === -1) return 1;
      if (idxB === -1) return -1;
      return idxA - idxB;
    });
  }

  const formatColumnName = (col: string) => {
    const formatMap: Record<string, string> = {
      'date': '기준일',
      'dubai': 'Dubai (USD/bbl)',
      'wti': 'WTI (USD/bbl)',
      'brent': 'Brent (USD/bbl)',
      'source': '데이터 소스',
      'inventory_mbbl': '재고량 (천 배럴)',
      'production_mbbl_d': '일일 생산량 (천 배럴/일)',
      'fed_rate': '기준금리 (%)',
      'dollar_index': '달러 인덱스',
      'title': '기사 제목',
      'description': '기사 요약',
      'url': '링크',
      'published_at': '발행 일시',
      'collected_at': '수집 일시'
    };
    return formatMap[col] || col;
  };

  return (
    <>
      <div className="data-tabs">
        {(['prices', 'macro', 'news', 'inventory', 'production'] as DataTab[]).map((tab) => (
          <button
            key={tab}
            className={`data-tab ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab === 'prices' ? '📈 유가' : tab === 'macro' ? '🏛 거시경제' : tab === 'news' ? '📰 뉴스' : tab === 'inventory' ? '🛢 재고' : '⚙️ 생산'}
          </button>
        ))}
      </div>

      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col}>{formatColumnName(col)}</th>
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
  const [subTab, setSubTab] = useState<'auto' | 'manual'>(() => {
    return (localStorage.getItem('crawlSubTab') as 'auto' | 'manual') || 'auto';
  });

  useEffect(() => {
    localStorage.setItem('crawlSubTab', subTab);
  }, [subTab]);
  const [bottomTab, setBottomTab] = useState<'history' | 'health' | 'integrity' | 'schema'>(() => {
    return (localStorage.getItem('crawlBottomTab') as 'history' | 'health' | 'integrity' | 'schema') || 'history';
  });

  useEffect(() => {
    localStorage.setItem('crawlBottomTab', bottomTab);
  }, [bottomTab]);

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
  const [endYear, setEndYear] = useState(2026);
  const [crawlMode, setCrawlMode] = useState<'range' | 'single'>('range');

  // Year Coverage Heatmap
  const [yearCoverage, setYearCoverage] = useState<YearCoverageItem[]>([]);

  // Article Search (History Hub)
  const [searchYear, setSearchYear] = useState<number | undefined>();
  const [searchSource, setSearchSource] = useState<string>('');
  const [searchKeyword, setSearchKeyword] = useState('');
  const [searchClsStatus, setSearchClsStatus] = useState('unclassified');
  const [searchResults, setSearchResults] = useState<{ total: number; items: CrawlSearchArticle[] }>({ total: 0, items: [] });
  const [searchOffset, setSearchOffset] = useState(0);
  const [searchLoading, setSearchLoading] = useState(false);
  const [selectedArticleIds, setSelectedArticleIds] = useState<Set<string>>(new Set());
  const [expandedArticleId, setExpandedArticleId] = useState<string | null>(null);
  const [deleteUndoTimer, setDeleteUndoTimer] = useState<number | null>(null);
  const [pendingDeleteIds, setPendingDeleteIds] = useState<string[]>([]);

  // History & Health
  const [history, setHistory] = useState<CrawlHistoryItem[]>([]);
  const [health, setHealth] = useState<SourceHealthItem[]>([]);

  // Integrity
  const [integrity, setIntegrity] = useState<IntegrityReport | null>(null);
  const [integrityTab, setIntegrityTab] = useState<'no_field' | 'cls_broken'>('no_field');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: 'ok' | 'err' } | null>(null);

  const toastTimer = useRef<number | null>(null);
  const showToast = (msg: string, type: 'ok' | 'err' = 'ok') => {
    setToast({ msg, type });
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 3000);
  };

  // Log Detail Modal
  const [isLogModalOpen, setIsLogModalOpen] = useState(false);
  const [selectedLogId, setSelectedLogId] = useState<number | null>(null);
  const [logArticles, setLogArticles] = useState<CrawlArticleDetail[]>([]);
  const [logModalLoading, setLogModalLoading] = useState(false);

  // Date Filter (legacy — used in loadAll)
  const [historyDateFilter] = useState('');

  const logEndRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const [sc, s, st, h, hl, ig, yc] = await Promise.all([
        fetchSchedulerStatus(),
        fetchCrawlStatus(),
        fetchCrawlStats(),
        fetchCrawlHistory(20, historyDateFilter || undefined),
        fetchSourceHealth(),
        fetchIntegrityReport(),
        fetchYearCoverage(),
      ]);
      setScheduler(sc);
      setIntervalHours(sc.interval_hours || 6);
      setStatus(s);
      setStats(st);
      setHistory(h);
      setHealth(hl);
      setIntegrity(ig);
      setYearCoverage(yc);
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
      showToast(sc.is_running ? "스케줄러가 시작되었습니다." : "스케줄러가 정지되었습니다.");
    } catch (e) {
      showToast(String(e), 'err');
    } finally {
      setActionLoading(false);
    }
  };

  const handleUpdateConfig = async () => {
    try {
      await updateSchedulerConfig(intervalHours);
      showToast(`스케줄 간격이 ${intervalHours}시간으로 변경되었습니다.`);
      loadAll();
    } catch (e) { showToast(String(e), 'err'); }
  };

  const handleTriggerNews = async () => {
    setActionLoading(true);
    try {
      const res = await triggerNewsCrawl();
      showToast(res.message);
      // 백그라운드 태스크가 시작되고 로그가 생성될 시간을 약간 부여한 후 갱신
      setTimeout(() => {
        loadAll();
      }, 1000);
    } catch (e) { showToast(String(e), 'err'); }
    setActionLoading(false);
  };

  // Legacy handlers kept for log detail modal reference
  // @ts-ignore Legacy handler for potential future use
  const _handleLogClick = async (log: CrawlHistoryItem) => { // eslint-disable-line
    if (log.source !== 'news' || log.status === 'running') return;
    setSelectedLogId(log.id);
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

  const handleStart = async () => {
    setActionLoading(true);
    try {
      const ey = crawlMode === 'single' ? startYear : endYear;
      const result = await startCrawl(target, startYear, ey);
      showToast(result.message);
      await loadAll();
    } catch (e) { showToast(`오류: ${e}`, 'err'); }
    setActionLoading(false);
  };

  const handleStop = async () => {
    setActionLoading(true);
    try {
      const result = await stopCrawl();
      showToast(result.message);
      await loadAll();
    } catch (e) { showToast(`오류: ${e}`, 'err'); }
    setActionLoading(false);
  };

  // Article Search
  const handleArticleSearch = useCallback(async (newOffset = 0) => {
    setSearchLoading(true);
    setSearchOffset(newOffset);
    try {
      const res = await searchCrawlArticles(
        searchYear, searchSource || undefined, searchKeyword || undefined, 
        searchClsStatus === 'all' ? undefined : searchClsStatus, 
        50, newOffset
      );
      setSearchResults(res);
      setSelectedArticleIds(new Set());
      setExpandedArticleId(null);
    } catch (e) { console.error(e); }
    setSearchLoading(false);
  }, [searchYear, searchSource, searchKeyword, searchClsStatus]);

  useEffect(() => {
    if (bottomTab === 'history') {
      handleArticleSearch(0);
    }
  }, [bottomTab, searchClsStatus]); // searchClsStatus가 변경될 때도 자동 검색되게 추가

  // Delete with undo
  const handleDeleteArticles = (ids: string[]) => {
    if (ids.length === 0) return;
    // Optimistically remove from results
    setPendingDeleteIds(ids);
    setSearchResults(prev => ({
      total: prev.total - ids.length,
      items: prev.items.filter(a => !ids.includes(a.id)),
    }));
    setSelectedArticleIds(new Set());
    showToast(`${ids.length}건 삭제됨 — 5초 후 확정`);

    const timer = window.setTimeout(async () => {
      try {
        await deleteCrawlArticles(ids);
        setPendingDeleteIds([]);
        setDeleteUndoTimer(null);
        loadAll();
      } catch (e) { showToast(`삭제 실패: ${e}`, 'err'); }
    }, 5000);
    setDeleteUndoTimer(timer);
  };

  const handleUndoDelete = () => {
    if (deleteUndoTimer) {
      clearTimeout(deleteUndoTimer);
      setDeleteUndoTimer(null);
    }
    setPendingDeleteIds([]);
    handleArticleSearch(searchOffset);
    showToast('삭제가 취소되었습니다.');
  };

  // Recrawl
  const handleRecrawlArticles = async (ids: string[]) => {
    if (ids.length === 0) return;
    setActionLoading(true);
    try {
      const res = await recrawlArticles(ids);
      showToast(res.message);
      setSelectedArticleIds(new Set());
      await handleArticleSearch(searchOffset);
      await loadAll();
    } catch (e) { showToast(`재수집 오류: ${e}`, 'err'); }
    setActionLoading(false);
  };

  const toggleArticleSelection = (id: string) => {
    const newSel = new Set(selectedArticleIds);
    if (newSel.has(id)) newSel.delete(id);
    else newSel.add(id);
    setSelectedArticleIds(newSel);
  };

  const toggleSelectAll = () => {
    if (selectedArticleIds.size === searchResults.items.length) {
      setSelectedArticleIds(new Set());
    } else {
      setSelectedArticleIds(new Set(searchResults.items.map(a => a.id)));
    }
  };

  const handleHold = async (ids: string[], holdStatus: number) => {
    if (ids.length === 0) return;
    try {
      await updateArticleHoldStatus(ids, holdStatus);
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

  // yearlyGroups kept for potential future use
  const _yearlyGroups: Record<string, Record<string, number>> = {};
  stats?.by_year?.forEach(({ year, data_source, count }) => {
    if (!_yearlyGroups[year]) _yearlyGroups[year] = {};
    _yearlyGroups[year][data_source] = count;
  });

  return (
    <>
      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', top: 20, right: 20, zIndex: 9999,
          padding: '10px 20px', borderRadius: 8, fontSize: '0.9em', fontWeight: 500,
          background: toast.type === 'ok' ? 'rgba(34,197,94,0.95)' : 'rgba(239,68,68,0.95)',
          color: '#fff', boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
          animation: 'fadeIn 0.2s ease-out',
        }}>
          {toast.type === 'ok' ? '✓' : '✕'} {toast.msg}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div className="data-tabs" style={{ margin: 0 }}>
          <button className={`data-tab ${subTab === 'auto' ? 'active' : ''}`} onClick={() => setSubTab('auto')}>
            🔄 자동 크롤링
          </button>
          <button className={`data-tab ${subTab === 'manual' ? 'active' : ''}`} onClick={() => setSubTab('manual')}>
            🔧 수동 크롤링
          </button>
        </div>
      </div>

      {subTab === 'auto' && (
        <div className="crawl-control-panel">
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
      )}

      {subTab === 'manual' && (
        <div className="crawl-control-panel">
          {/* Year Coverage Heatmap */}
          <div className="crawl-control-header" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 12, padding: '16px 20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#e4e8ef' }}>📊 연도별 데이터 커버리지 (2000~현재)</span>
              <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)' }}>셀 클릭 → 연도 자동 설정</span>
            </div>
            <div className="year-coverage-heatmap">
              {yearCoverage.map(yc => {
                const maxCount = Math.max(1, ...yearCoverage.map(y => y.total));
                const intensity = yc.total / maxCount;
                const bg = yc.total === 0 ? 'rgba(255,77,77,0.15)'
                  : intensity < 0.3 ? 'rgba(255,184,77,0.25)'
                  : intensity < 0.7 ? 'rgba(0,212,150,0.25)'
                  : 'rgba(0,212,150,0.5)';
                return (
                  <div key={yc.year} className="heatmap-cell" style={{ background: bg }}
                    title={`${yc.year}년: ${yc.total}건 (NYT ${yc.nyt}, Guardian ${yc.guardian})`}
                    onClick={() => { setStartYear(yc.year); if (crawlMode === 'single') setEndYear(yc.year); }}>
                    <span className="heatmap-year">{String(yc.year).slice(2)}</span>
                    <span className="heatmap-count">{yc.total > 0 ? yc.total : '—'}</span>
                  </div>
                );
              })}
            </div>
            {(() => {
              const gaps = yearCoverage.filter(y => y.total === 0 && y.year <= new Date().getFullYear());
              if (gaps.length === 0) return null;
              const gapYears = gaps.map(g => g.year);
              return (
                <div className="data-gap-suggest" onClick={() => { setStartYear(gapYears[0]); setEndYear(gapYears[gapYears.length - 1]); setCrawlMode('range'); }}>
                  💡 데이터 공백: {gapYears.length <= 5 ? gapYears.join(', ') : `${gapYears[0]}~${gapYears[gapYears.length-1]} (${gapYears.length}개 연도)`}년 — 클릭하여 수집
                </div>
              );
            })()}
          </div>

          {/* Mode Toggle + Presets */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 16, marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
            <div className="crawl-mode-toggle">
              <button className={crawlMode === 'range' ? 'active' : ''} onClick={() => setCrawlMode('range')}>📅 범위 수집</button>
              <button className={crawlMode === 'single' ? 'active' : ''} onClick={() => setCrawlMode('single')}>📌 단독 수집</button>
            </div>
            <div className="crawl-presets">
              <button className="crawl-preset-btn" onClick={() => { setCrawlMode('range'); setStartYear(new Date().getFullYear() - 4); setEndYear(new Date().getFullYear()); }}>최근 5년</button>
              <button className="crawl-preset-btn" onClick={() => {
                const gaps = yearCoverage.filter(y => y.total === 0 && y.year <= new Date().getFullYear());
                if (gaps.length > 0) { setCrawlMode('range'); setStartYear(gaps[0].year); setEndYear(gaps[gaps.length-1].year); }
              }}>빈 연도만</button>
              <button className="crawl-preset-btn" onClick={() => { setCrawlMode('range'); setStartYear(2000); setEndYear(new Date().getFullYear()); }}>전체</button>
            </div>
          </div>

          {/* Crawl Form */}
          <div className="crawl-controls">
            <div className="crawl-input-group">
              <label>{crawlMode === 'single' ? '수집 연도' : '시작 연도'}</label>
              <input type="number" className="filter-input" value={startYear}
                onChange={(e) => { setStartYear(Number(e.target.value)); if (crawlMode === 'single') setEndYear(Number(e.target.value)); }}
                disabled={status?.is_running} min={2000} max={2026} />
            </div>
            {crawlMode === 'range' && (
              <div className="crawl-input-group">
                <label>종료 연도</label>
                <input type="number" className="filter-input" value={endYear}
                  onChange={(e) => setEndYear(Number(e.target.value))}
                  disabled={status?.is_running} min={startYear} max={2026} />
              </div>
            )}
            <div className="crawl-input-group">
              <label>목표 건수</label>
              <input type="number" className="filter-input" value={target}
                onChange={(e) => setTarget(Number(e.target.value))}
                disabled={status?.is_running} min={100} max={10000} step={100} />
            </div>
            <div className="crawl-buttons" style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: '8px', gap: 8 }}>
              {status?.is_running ? (
                <button className="crawl-stop-btn" onClick={handleStop} disabled={actionLoading}>⏹ 크롤링 중지</button>
              ) : (
                <button className="crawl-start-btn" onClick={handleStart} disabled={actionLoading}>🚀 크롤링 시작</button>
              )}
            </div>
          </div>

          {/* Pre-crawl Estimate */}
          {!status?.is_running && (
            <div className="crawl-estimate">
              {(() => {
                const numYears = crawlMode === 'single' ? 1 : Math.max(1, endYear - startYear + 1);
                const estArticles = Math.min(target, numYears * Math.ceil(target / numYears));
                const estTime = numYears * 15;
                return `예상: ${numYears}개 연도 × ~${Math.ceil(target/numYears)}건 = 약 ${estArticles.toLocaleString()}건, 소요 ~${estTime < 60 ? estTime + '초' : Math.ceil(estTime/60) + '분'}`;
              })()}
            </div>
          )}

          {/* Real-time Progress Dashboard */}
          {status?.is_running && (
            <div style={{ marginTop: 16 }}>
              <div className="crawl-progress">
                <div className="crawl-progress-header">
                  <span>{status.year_start && status.year_end ? `${status.year_start}→${status.year_end}: ${status.years_completed}/${status.years_total} 연도` : `${status.current_year}년 수집 중`}</span>
                  <span>{status.collected?.toLocaleString()} / {status.target?.toLocaleString()} 건 ({progressPct.toFixed(1)}%)</span>
                </div>
                <div className="rate-limit-bar" style={{ height: 8 }}>
                  <div className="rate-limit-fill safe" style={{ width: `${progressPct}%`, transition: 'width 0.5s ease' }} />
                </div>
              </div>
              <div className="crawl-live-cards">
                <div className="crawl-live-card">
                  <div className="crawl-live-card-label">📰 NYT</div>
                  <div className="crawl-live-card-value">{status.nyt_collected}</div>
                  {status.current_source === 'nyt' && <div className="crawl-live-card-active">수집 중...</div>}
                </div>
                <div className="crawl-live-card">
                  <div className="crawl-live-card-label">🗞️ Guardian</div>
                  <div className="crawl-live-card-value">{status.guardian_collected}</div>
                  {status.current_source === 'guardian' && <div className="crawl-live-card-active">수집 중...</div>}
                </div>
                <div className="crawl-live-card">
                  <div className="crawl-live-card-label">🔄 중복 제거</div>
                  <div className="crawl-live-card-value">{status.dupes_removed}</div>
                </div>
                <div className="crawl-live-card">
                  <div className="crawl-live-card-label">⏱️ 경과</div>
                  <div className="crawl-live-card-value">{status.elapsed_seconds < 60 ? `${status.elapsed_seconds}s` : `${Math.floor(status.elapsed_seconds / 60)}m ${status.elapsed_seconds % 60}s`}</div>
                </div>
              </div>
            </div>
          )}

          {/* Real-time Year Breakdown Table */}
          {(status?.year_breakdown && status.year_breakdown.length > 0) && (
            <div className="year-breakdown-container" style={{ marginTop: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#e4e8ef', marginBottom: 8 }}>📊 연도별 수집 상세 내역</div>
              <div className="admin-table-container" style={{ maxHeight: 250, overflowY: 'auto' }}>
                <table className="admin-table" style={{ fontSize: 12 }}>
                  <thead style={{ position: 'sticky', top: 0, zIndex: 1, background: 'rgba(20,24,36,0.95)', backdropFilter: 'blur(8px)' }}>
                    <tr>
                      <th style={{ width: 60 }}>연도</th>
                      <th style={{ width: 100 }}>NYT (신규/조회)</th>
                      <th style={{ width: 120 }}>Guardian (신규/조회)</th>
                      <th style={{ width: 80 }}>URL 스킵</th>
                      <th style={{ width: 80 }}>최종 저장</th>
                      <th>오류 정보</th>
                    </tr>
                  </thead>
                  <tbody>
                    {status.year_breakdown.map((y, i) => (
                      <tr key={i} style={{ backgroundColor: y.error ? 'rgba(255,77,77,0.05)' : undefined }}>
                        <td style={{ fontWeight: 600 }}>{y.year}</td>
                        <td>{y.nyt_new} / {y.nyt_fetched}</td>
                        <td>{y.guardian_new} / {y.guardian_fetched}</td>
                        <td style={{ color: y.skipped_existing > 0 ? '#ffb84d' : 'inherit' }}>{y.skipped_existing}</td>
                        <td style={{ fontWeight: 600, color: y.saved > 0 ? '#00D496' : 'inherit' }}>{y.saved}</td>
                        <td style={{ color: y.error ? '#ff4d4d' : 'rgba(255,255,255,0.4)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={y.error || ''}>
                          {y.error || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Live Log Console */}
          {status?.recent_logs && status.recent_logs.length > 0 && (
            <div className="crawl-live-console">
              <div className="console-header"><span>🖥️ 라이브 로그</span><span style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)' }}>{status.recent_logs.length}줄</span></div>
              <div className="console-body">
                {status.recent_logs.map((line, i) => (
                  <div key={i} className={`log-line ${line.includes('ERROR') || line.includes('error') ? 'error' : ''}`}>{line}</div>
                ))}
                <div ref={logEndRef} />
              </div>
            </div>
          )}

          {/* Completion Banner */}
          {!status?.is_running && status?.collected && status.collected > 0 && status?.elapsed_seconds > 0 && (
            <div className="crawl-complete-banner">
              ✅ 크롤링 완료! 총 {status.collected.toLocaleString()}건 수집 (NYT {status.nyt_collected}, Guardian {status.guardian_collected}) — {status.elapsed_seconds}초 소요
            </div>
          )}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '24px', marginBottom: '16px' }}>
        <div className="data-tabs" style={{ margin: 0 }}>
          <button className={`data-tab ${bottomTab === 'history' ? 'active' : ''}`} onClick={() => { setBottomTab('history'); }}>
            🔍 데이터 관리
          </button>
          <button className={`data-tab ${bottomTab === 'health' ? 'active' : ''}`} onClick={() => setBottomTab('health')}>
            🏥 소스 건강도
          </button>
          <button className={`data-tab ${bottomTab === 'integrity' ? 'active' : ''}`} onClick={() => setBottomTab('integrity')}>
            🔍 데이터 완결성 검증
          </button>
          <button className={`data-tab ${bottomTab === 'schema' ? 'active' : ''}`} onClick={() => setBottomTab('schema')}>
            📊 데이터 스키마
          </button>
        </div>
      </div>

      {bottomTab === 'health' && (
        <div className="crawl-control-panel">
          <div className="admin-table-container">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>분류</th>
                  <th>소스</th>
                  <th>최신 데이터</th>
                  <th>업데이트 주기</th>
                  <th>에러율</th>
                  <th>평균 응답</th>
                </tr>
              </thead>
              <tbody>
                {health.map(h => {
                  const errorRate = h.total_runs ? ((h.error_runs || 0) / h.total_runs) * 100 : 0;
                  const daysDiff = h.newest_article ? (new Date().getTime() - new Date(h.newest_article).getTime()) / (1000 * 3600 * 24) : Infinity;

                  let isStale = false;
                  let isInactive = false;

                  if (h.data_source === 'opinet') {
                    isStale = daysDiff > 4;    // 주말 휴장 고려 4일
                    isInactive = daysDiff > 14;
                  } else if (['eia_inventory', 'eia_production', 'fred'].includes(h.data_source)) {
                    isStale = daysDiff > 12;   // 주간 리포트 딜레이 고려 12일
                    isInactive = daysDiff > 30;
                  } else {
                    isStale = daysDiff > 7;    // 뉴스 수집 지연 7일
                    isInactive = daysDiff > 30;
                  }

                  const getSourceInfo = (src: string) => {
                    if (src === 'opinet') return { cat: '유가 (Price)', cycle: '매일 (Daily)', desc: '한국석유공사 Opinet (국제 및 국내 유가 데이터)' };
                    if (src === 'eia_inventory') return { cat: '수급 (Supply)', cycle: '매주 수요일 (금요일 마감 기준)', desc: '미국 에너지정보청(EIA) 주간 원유 재고 데이터' };
                    if (src === 'eia_production') return { cat: '수급 (Supply)', cycle: '매주 수요일 (금요일 마감 기준)', desc: '미국 에너지정보청(EIA) 주간 원유 생산량 데이터' };
                    if (src === 'fred') return { cat: '거시경제 (Macro)', cycle: '매주 월요일 (금요일 마감 기준)', desc: '세인트루이스 연방준비은행 (달러 인덱스, 금리 등)' };
                    return { cat: '뉴스 (News)', cycle: '수시 (Real-time)', desc: '글로벌 원유 시장 동향 뉴스 기사 수집' };
                  };

                  const info = getSourceInfo(h.data_source);

                  return (
                    <tr key={h.data_source} title={info.desc} style={{ cursor: 'help' }}>
                      <td><span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.6)' }}>{info.cat}</span></td>
                      <td><SourceTag source={h.data_source} /></td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ color: '#fff' }}>{h.newest_article?.slice(0, 10) || '—'}</span>
                          {!h.newest_article ? <span className="issue-badge" style={{ background: 'rgba(255, 255, 255, 0.1)', color: '#aaa', borderColor: 'rgba(255, 255, 255, 0.2)' }}>데이터 없음</span> :
                            isInactive ? <span className="issue-badge" style={{ background: 'rgba(255, 77, 77, 0.1)', color: '#ff4d4d', borderColor: 'rgba(255, 77, 77, 0.3)' }}>❌ 수집 단절</span> :
                              isStale ? <span className="issue-badge" style={{ background: 'rgba(255, 184, 77, 0.1)', color: '#ffb84d', borderColor: 'rgba(255, 184, 77, 0.3)' }}>⚠️ 지연됨</span> :
                                <span className="issue-badge" style={{ background: 'rgba(0, 212, 150, 0.1)', color: '#00D496', borderColor: 'rgba(0, 212, 150, 0.3)' }}>✅ 최신 상태</span>}
                        </div>
                      </td>
                      <td style={{ color: 'rgba(255,255,255,0.8)', fontSize: '13px' }}>{info.cycle}</td>
                      <td>{errorRate.toFixed(1)}%</td>
                      <td>{h.avg_duration_ms ? `${h.avg_duration_ms}ms` : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {bottomTab === 'history' && (
        <div className="crawl-control-panel">
          {/* Search Filters */}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: 16 }}>
            <div className="crawl-input-group" style={{ margin: 0 }}>
              <label style={{ fontSize: 11 }}>연도</label>
              <select className="filter-input" value={searchYear || ''} onChange={e => setSearchYear(e.target.value ? Number(e.target.value) : undefined)}
                style={{ minWidth: 90, background: 'rgba(0,0,0,0.3)', color: '#fff', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 6, padding: '6px 8px' }}>
                <option value="">전체</option>
                {yearCoverage.filter(y => y.total > 0).map(y => (
                  <option key={y.year} value={y.year}>{y.year} ({y.total}건)</option>
                ))}
              </select>
            </div>
            <div className="crawl-input-group" style={{ margin: 0 }}>
              <label style={{ fontSize: 11 }}>소스</label>
              <select className="filter-input" value={searchSource} onChange={e => setSearchSource(e.target.value)}
                style={{ minWidth: 100, background: 'rgba(0,0,0,0.3)', color: '#fff', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 6, padding: '6px 8px' }}>
                <option value="">전체</option>
                <option value="nyt">NYT</option>
                <option value="guardian">Guardian</option>
              </select>
            </div>
            <div className="crawl-input-group" style={{ margin: 0 }}>
              <label style={{ fontSize: 11 }}>분류</label>
              <select className="filter-input" value={searchClsStatus} onChange={e => setSearchClsStatus(e.target.value)}
                style={{ minWidth: 100, background: 'rgba(0,0,0,0.3)', color: '#fff', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 6, padding: '6px 8px' }}>
                <option value="all">전체</option>
                <option value="classified">분류완료</option>
                <option value="irrelevant">관련성 없음</option>
                <option value="unclassified">미분류</option>
                <option value="error">에러</option>
              </select>
            </div>
            <div className="crawl-input-group" style={{ margin: 0, flex: 1, minWidth: 150 }}>
              <label style={{ fontSize: 11 }}>키워드</label>
              <input type="text" className="filter-input" value={searchKeyword} onChange={e => setSearchKeyword(e.target.value)}
                placeholder="제목/설명 검색..." onKeyDown={e => e.key === 'Enter' && handleArticleSearch()}
                style={{ background: 'rgba(0,0,0,0.3)', color: '#fff', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 6, padding: '6px 8px' }} />
            </div>
            <button className="action-btn small primary" onClick={() => handleArticleSearch()} disabled={searchLoading}
              style={{ padding: '6px 16px', whiteSpace: 'nowrap' }}>
              🔍 검색
            </button>
          </div>

          {/* Results Info */}
          {searchResults.total > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, fontSize: 13, color: 'rgba(255,255,255,0.6)' }}>
              <span>총 {searchResults.total.toLocaleString()}건 중 {searchOffset + 1}~{Math.min(searchOffset + 50, searchResults.total)}</span>
              {selectedArticleIds.size > 0 && <span style={{ color: '#00D4FF' }}>{selectedArticleIds.size}건 선택됨</span>}
            </div>
          )}

          {/* Article Table */}
          <div className="admin-table-container" style={{ maxHeight: 500, overflowY: 'auto' }}>
            {searchLoading ? (
              <div className="admin-skeleton" style={{ height: 200 }} />
            ) : searchResults.items.length === 0 ? (
              <div className="admin-empty-text" style={{ padding: '40px 0', textAlign: 'center' }}>
                검색 조건을 설정하고 🔍 검색을 클릭하세요
              </div>
            ) : (
              <table className="admin-table">
                <thead>
                  <tr>
                    <th style={{ width: 36 }}>
                      <input type="checkbox" checked={selectedArticleIds.size === searchResults.items.length && searchResults.items.length > 0}
                        onChange={toggleSelectAll} style={{ cursor: 'pointer' }} />
                    </th>
                    <th>발행일</th>
                    <th>소스</th>
                    <th>기사 제목</th>
                    <th>설명</th>
                    <th>분류</th>
                  </tr>
                </thead>
                <tbody>
                  {searchResults.items.map(a => (
                    <React.Fragment key={a.id}>
                      <tr
                        className={`clickable-row ${expandedArticleId === a.id ? 'expanded' : ''}`}
                        style={{ backgroundColor: selectedArticleIds.has(a.id) ? 'rgba(0,212,255,0.08)' : undefined }}
                      >
                        <td onClick={e => e.stopPropagation()}>
                          <input type="checkbox" checked={selectedArticleIds.has(a.id)}
                            onChange={() => toggleArticleSelection(a.id)} style={{ cursor: 'pointer' }} />
                        </td>
                        <td style={{ whiteSpace: 'nowrap', fontSize: 12 }}>{a.published_at?.slice(0, 10) || '—'}</td>
                        <td><SourceTag source={a.data_source || 'unknown'} /></td>
                        <td style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', cursor: 'pointer' }}
                          onClick={() => setExpandedArticleId(expandedArticleId === a.id ? null : a.id)}>
                          {a.title || '(제목 없음)'}
                        </td>
                        <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12, color: 'rgba(255,255,255,0.5)' }}
                          title={a.description}>
                          {a.description?.slice(0, 80) || '—'}
                        </td>
                        <td>
                          {a.is_classified === 1 ? (
                            <span className="issue-badge" style={{ background: 'rgba(0,212,150,0.1)', color: '#00D496', borderColor: 'rgba(0,212,150,0.3)' }}>
                              {a.ai_category || '분류됨'}
                            </span>
                          ) : a.is_classified === -1 ? (
                            <span className="issue-badge" style={{ background: 'rgba(255,77,77,0.1)', color: '#ff4d4d', borderColor: 'rgba(255,77,77,0.3)' }}>에러</span>
                          ) : (
                            <span className="issue-badge" style={{ background: 'rgba(255,255,255,0.05)', color: '#999', borderColor: 'rgba(255,255,255,0.1)' }}>미분류</span>
                          )}
                        </td>
                      </tr>
                      {/* Inline Expansion Panel */}
                      {expandedArticleId === a.id && (
                        <tr className="article-expand-row">
                          <td colSpan={6}>
                            <div className="article-expand-panel">
                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                                <div>
                                  <div className="expand-label">제목</div>
                                  <div style={{ color: '#fff', fontWeight: 500 }}>{a.title}</div>
                                </div>
                                <div>
                                  <div className="expand-label">URL</div>
                                  <a href={a.url} target="_blank" rel="noreferrer" style={{ color: '#00D4FF', fontSize: 12, wordBreak: 'break-all' }}>{a.url}</a>
                                </div>
                              </div>
                              <div style={{ marginTop: 12 }}>
                                <div className="expand-label">설명</div>
                                <div style={{ color: 'rgba(255,255,255,0.8)', fontSize: 13, lineHeight: 1.5 }}>{a.description || '(설명 없음)'}</div>
                              </div>
                              <div style={{ display: 'flex', gap: 16, marginTop: 12, fontSize: 12 }}>
                                <span>소스: <strong>{a.source_name || a.data_source}</strong></span>
                                <span>발행: <strong>{a.published_at}</strong></span>
                                <span>수집: <strong>{a.collected_at}</strong></span>
                                {a.ai_category && <span>카테고리: <strong>{a.ai_category}</strong></span>}
                                {a.ai_impact_score != null && <span>영향도: <strong>{a.ai_impact_score}</strong></span>}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Pagination */}
          {searchResults.total > 50 && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 12 }}>
              <button className="action-btn small" disabled={searchOffset === 0} onClick={() => handleArticleSearch(Math.max(0, searchOffset - 50))}>← 이전</button>
              <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.6)', alignSelf: 'center' }}>
                {Math.floor(searchOffset / 50) + 1} / {Math.ceil(searchResults.total / 50)} 페이지
              </span>
              <button className="action-btn small" disabled={searchOffset + 50 >= searchResults.total} onClick={() => handleArticleSearch(searchOffset + 50)}>다음 →</button>
            </div>
          )}

          {/* Floating Action Bar */}
          {selectedArticleIds.size > 0 && (
            <div className="article-action-bar">
              <span style={{ fontSize: 13 }}>{selectedArticleIds.size}건 선택</span>
              <button className="action-btn small secondary" onClick={() => handleRecrawlArticles(Array.from(selectedArticleIds))} disabled={actionLoading}>
                🔄 재수집
              </button>
              <button className="action-btn small danger" onClick={() => handleDeleteArticles(Array.from(selectedArticleIds))}>
                🗑️ 삭제
              </button>
              <button className="action-btn small" onClick={() => setSelectedArticleIds(new Set())}>
                선택 해제
              </button>
            </div>
          )}

          {/* Undo Toast */}
          {pendingDeleteIds.length > 0 && (
            <div className="undo-toast" onClick={handleUndoDelete}>
              ↩️ {pendingDeleteIds.length}건 삭제 대기 중 — 클릭하여 되돌리기
            </div>
          )}
        </div>
      )}

      {bottomTab === 'integrity' && integrity && (
        <div className="crawl-control-panel">
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

      {bottomTab === 'schema' && (
        <div className="crawl-control-panel">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '20px' }}>
            {[
              {
                title: '유가 수집 (Opinet)',
                table: 'oil_prices',
                desc: '국내외 원유 가격 정보',
                columns: [
                  { name: 'date', type: 'VARCHAR(20)', desc: '기준일 (YYYY-MM-DD)' },
                  { name: 'dubai', type: 'FLOAT', desc: '두바이유 (USD/bbl)' },
                  { name: 'wti', type: 'FLOAT', desc: '서부텍사스산원유 (USD/bbl)' },
                  { name: 'brent', type: 'FLOAT', desc: '브렌트유 (USD/bbl)' },
                  { name: 'source', type: 'VARCHAR(50)', desc: '데이터 소스' }
                ]
              },
              {
                title: '재고 수집 (EIA Inventory)',
                table: 'oil_inventory',
                desc: '미국 원유 재고량',
                columns: [
                  { name: 'date', type: 'VARCHAR(20)', desc: '기준 주간 마감일' },
                  { name: 'inventory_mbbl', type: 'FLOAT', desc: '재고량 (단위: 천 배럴)' }
                ]
              },
              {
                title: '생산량 수집 (EIA Production)',
                table: 'oil_production',
                desc: '미국 원유 생산량',
                columns: [
                  { name: 'date', type: 'VARCHAR(20)', desc: '기준 주간 마감일' },
                  { name: 'production_mbbl_d', type: 'FLOAT', desc: '일일 생산량 (단위: 천 배럴/일)' }
                ]
              },
              {
                title: '거시경제 수집 (FRED)',
                table: 'macro_indicators',
                desc: '주요 거시 경제 지표',
                columns: [
                  { name: 'date', type: 'VARCHAR(20)', desc: '기준일 (YYYY-MM-DD)' },
                  { name: 'fed_rate', type: 'FLOAT', desc: '미 연준 기준금리 (%)' },
                  { name: 'dollar_index', type: 'FLOAT', desc: '명목 달러 인덱스 (Broad)' }
                ]
              },
              {
                title: '뉴스 수집 (News)',
                table: 'news_articles',
                desc: '석유/에너지 관련 글로벌 기사',
                columns: [
                  { name: 'id', type: 'VARCHAR', desc: '고유 해시 ID' },
                  { name: 'title', type: 'VARCHAR', desc: '기사 제목' },
                  { name: 'description', type: 'TEXT', desc: '기사 요약' },
                  { name: 'source', type: 'VARCHAR', desc: '출처 (NYT, Guardian 등)' },
                  { name: 'url', type: 'VARCHAR', desc: '기사 링크' },
                  { name: 'published_at', type: 'VARCHAR(50)', desc: '발행 일시' }
                ]
              }
            ].map(s => (
              <div key={s.table} style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', padding: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <h4 style={{ margin: 0, color: '#fff', fontSize: '15px' }}>{s.title}</h4>
                  <span className="source-tag" style={{ fontSize: '11px', background: 'rgba(255,255,255,0.1)' }}>{s.table}</span>
                </div>
                <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '12px', margin: '0 0 16px 0' }}>{s.desc}</p>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                      <th style={{ textAlign: 'left', padding: '8px 4px', color: 'rgba(255,255,255,0.5)', fontWeight: 'normal' }}>Column</th>
                      <th style={{ textAlign: 'left', padding: '8px 4px', color: 'rgba(255,255,255,0.5)', fontWeight: 'normal' }}>Type</th>
                      <th style={{ textAlign: 'left', padding: '8px 4px', color: 'rgba(255,255,255,0.5)', fontWeight: 'normal' }}>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {s.columns.map(c => (
                      <tr key={c.name} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '8px 4px', color: '#00D496', fontFamily: 'monospace' }}>{c.name}</td>
                        <td style={{ padding: '8px 4px', color: '#ffb84d', fontFamily: 'monospace' }}>{c.type}</td>
                        <td style={{ padding: '8px 4px', color: 'rgba(255,255,255,0.8)' }}>{c.desc}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Log Detail Modal */}
      {isLogModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsLogModalOpen(false)}>
          <div className="crawl-detail-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>크롤링 상세 내역 (작업 #{selectedLogId})</h3>
              <button className="close-btn" onClick={() => setIsLogModalOpen(false)}>✕</button>
            </div>
            <div className="modal-content">
              {logModalLoading ? (
                <div className="admin-skeleton" style={{ height: 200 }} />
              ) : logArticles.length === 0 ? (
                <div className="admin-empty-text">해당 작업에서 신규 수집된 기사가 없습니다.</div>
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
    </>
  );
};

// ═══════════════════════════════════════════════
// Pipeline Management Section (별도 파일로 분리)
// ═══════════════════════════════════════════════
const PipelineSection = React.lazy(() => import('./PipelineSection'));

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
          <h1>OilLens Admin</h1>
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
      {activeTab === 'pipeline' && <React.Suspense fallback={<div>Loading...</div>}><PipelineSection /></React.Suspense>}
      {activeTab === 'crawl' && <CrawlCenterSection />}
      {activeTab === 'logs' && <LogsSection />}
      {activeTab === 'data' && <DataExplorerSection />}
      {activeTab === 'trigger' && <TriggerSection />}
    </div>
  );
};
