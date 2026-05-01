import React, { useState, useEffect, useRef } from 'react';
import {
  fetchClassificationStats,
  fetchPipelineArticles,
  deletePipelineArticles,
  retryPipelineItems,
  fetchPipelineJobs,
} from '../../services/adminApi';
import type {
  ClassificationStats, PipelineArticle, PipelineJob
} from '../../services/adminApi';

const CATEGORY_KR: Record<string, string> = {
  geopolitics: '지정학', supply: '공급', demand: '수요',
  macro: '거시경제', climate: '기후/ESG', speculation: '투기/심리', other: '기타',
};

const SourceTag: React.FC<{ source: string }> = ({ source }) => (
  <span className={`source-tag ${source}`}>{source.toUpperCase()}</span>
);

const formatDate = (d: string) => {
  if (!d) return '-';
  try { return new Date(d).toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }); }
  catch { return d.slice(0, 16); }
};

type PipelineTab = 'stats' | 'articles' | 'jobs';
const PAGE_SIZE = 30;

const PipelineSectionV2: React.FC = () => {
  const [subTab, setSubTab] = useState<PipelineTab>('stats');

  const [clsStats, setClsStats] = useState<ClassificationStats | null>(null);
  const [articles, setArticles] = useState<PipelineArticle[]>([]);
  const [articlesTotal, setArticlesTotal] = useState(0);
  const [articleFilter, setArticleFilter] = useState('all');
  const [articlePage, setArticlePage] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [expandedArticleId, setExpandedArticleId] = useState<string | null>(null);
  const [jobs, setJobs] = useState<PipelineJob[]>([]);
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ msg: string; type: 'ok' | 'err' } | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const refreshRef = useRef<number | null>(null);
  const toastTimer = useRef<number | null>(null);

  const showToast = (msg: string, type: 'ok' | 'err' = 'ok') => {
    setToast({ msg, type });
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 3000);
  };

  const loadStats = async () => {
    const cls = await fetchClassificationStats();
    setClsStats(cls);
  };
  const loadArticles = async (filter = articleFilter, page = articlePage) => {
    const res = await fetchPipelineArticles(filter, PAGE_SIZE, page * PAGE_SIZE);
    setArticles(res.items);
    setArticlesTotal(res.total);
  };
  const loadJobs = async () => { setJobs(await fetchPipelineJobs()); };

  useEffect(() => {
    (async () => {
      setLoading(true);
      try { await Promise.all([loadStats(), loadArticles(), loadJobs()]); }
      catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, []);

  useEffect(() => {
    const hasActive = jobs.some(j => j.status === 'queued' || j.status === 'running');
    if (hasActive) {
      refreshRef.current = window.setInterval(async () => {
        try { await loadJobs(); await loadStats(); } catch {}
      }, 4000);
    }
    return () => { if (refreshRef.current) { clearInterval(refreshRef.current); refreshRef.current = null; } };
  }, [jobs]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try { await Promise.all([loadStats(), loadArticles(), loadJobs()]); showToast('새로고침 완료'); }
    catch { showToast('새로고침 실패', 'err'); }
    finally { setRefreshing(false); }
  };
  const handleRetry = async (ids: string[]) => {
    try { await retryPipelineItems(ids); await loadJobs(); setSelectedIds(new Set()); showToast(`${ids.length}건 재시도 요청 완료`); setSubTab('jobs'); }
    catch { showToast('재시도 요청에 실패했습니다.', 'err'); }
  };
  const handleDelete = async (ids?: string[]) => {
    const targets = ids || Array.from(selectedIds);
    if (targets.length === 0) return;
    if (!confirm(`선택한 ${targets.length}건의 기사를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.`)) return;
    try {
      const res = await deletePipelineArticles(targets);
      showToast(`${res.deleted}건 삭제 완료`);
      setSelectedIds(new Set()); setExpandedArticleId(null);
      await loadArticles(); await loadStats();
    } catch { showToast('삭제에 실패했습니다.', 'err'); }
  };
  const goToArticles = (filter: string) => { setSubTab('articles'); handleFilterChange(filter); };
  const toggleSelect = (id: string) => setSelectedIds(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const toggleSelectAll = () => selectedIds.size === articles.length ? setSelectedIds(new Set()) : setSelectedIds(new Set(articles.map(a => a.id)));
  const handleFilterChange = async (f: string) => { setArticleFilter(f); setArticlePage(0); setSelectedIds(new Set()); setExpandedArticleId(null); await loadArticles(f, 0); };
  const handlePageChange = async (p: number) => { setArticlePage(p); setSelectedIds(new Set()); setExpandedArticleId(null); await loadArticles(articleFilter, p); };

  if (loading) return (
    <div className="overview-grid">
      {[...Array(4)].map((_, i) => <div key={i} className="overview-card"><div className="admin-skeleton" style={{ width: '60%', height: 14, marginBottom: 10 }} /><div className="admin-skeleton" style={{ width: '40%', height: 32 }} /></div>)}
    </div>
  );

  const maxCatCount = clsStats ? Math.max(1, ...clsStats.category_distribution.map(c => c.count)) : 1;

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

      {/* Sub-tab navigation */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div className="data-tabs" style={{ margin: 0 }}>
          {([
            { id: 'stats' as PipelineTab, label: '📊 현황', badge: '' },
            { id: 'articles' as PipelineTab, label: '📝 기사 관리', badge: clsStats ? `${clsStats.total.toLocaleString()}` : '' },
            { id: 'jobs' as PipelineTab, label: '⚙️ 작업 이력', badge: jobs.length ? `${jobs.length}` : '' },
          ]).map(t => (
            <button key={t.id} className={`data-tab ${subTab === t.id ? 'active' : ''}`} onClick={() => setSubTab(t.id)}>
              {t.label}
              {t.badge && <span style={{ marginLeft: 6, opacity: 0.6, fontSize: '0.85em' }}>({t.badge})</span>}
              {t.id === 'jobs' && jobs.some(j => j.status === 'running') && (
                <span style={{ marginLeft: 6, width: 8, height: 8, borderRadius: '50%', background: '#4a9eff', display: 'inline-block', animation: 'pulse 1.2s ease-in-out infinite' }} />
              )}
            </button>
          ))}
        </div>
        <button className="action-btn secondary" onClick={handleRefresh} disabled={refreshing} style={{ padding: '6px 14px', fontSize: '0.85em' }}>
          {refreshing ? '⟳ 새로고침 중...' : '🔄 새로고침'}
        </button>
      </div>

      {/* ═══ TAB 1: 현황 ═══ */}
      {subTab === 'stats' && clsStats && (
        <div className="crawl-control-panel">
          <div className="crawl-control-header">
            <div className="crawl-status-indicator">
              <span className="crawl-status-text">파이프라인 통계</span>
            </div>
          </div>
          <div className="overview-grid">
            {[
              { label: '전체 기사', value: clsStats.total, color: '', filter: 'all' },
              { label: 'AI 분류 완료', value: clsStats.classified, color: 'var(--color-success)', filter: 'classified' },
              { label: '분류 대기', value: clsStats.unclassified, color: clsStats.unclassified > 0 ? 'var(--color-warning)' : '', filter: 'pending' },
              { label: '분류 에러', value: clsStats.failed, color: clsStats.failed > 0 ? 'var(--color-danger)' : '', filter: 'failed', border: clsStats.failed > 0 },
            ].map((c, i) => (
              <div key={i} className="overview-card" onClick={() => goToArticles(c.filter)} style={{ cursor: 'pointer', transition: 'transform 0.15s', ...(c.border ? { borderLeft: '4px solid var(--color-danger)' } : {}) }} title={`클릭하여 ${c.label} 기사 목록 보기`}>
                <div className="overview-card-label">{c.label}</div>
                <div className="overview-card-value" style={c.color ? { color: c.color } : {}}>{c.value.toLocaleString()}</div>
                <div style={{ fontSize: '0.75em', color: '#666', marginTop: 4 }}>클릭하여 목록 보기 →</div>
              </div>
            ))}
          </div>
          <div className="pipeline-progress-section">
            <div className="pipeline-progress-header"><span>전체 분류 진행률</span><span>{clsStats.classification_rate}%</span></div>
            <div className="rate-limit-bar" style={{ height: 10 }}>
              <div className={`rate-limit-fill ${clsStats.classification_rate > 80 ? 'safe' : clsStats.classification_rate > 50 ? 'warning' : 'danger'}`} style={{ width: `${clsStats.classification_rate}%` }} />
            </div>
          </div>
          <h3 className="section-title" style={{ marginTop: '32px' }}>카테고리별 분류 분포</h3>
          <div className="crawl-yearly-chart">
            {clsStats.category_distribution.map(cat => (
              <div className="crawl-year-row" key={cat.category}>
                <span className="crawl-year-label" style={{ width: '80px', textAlign: 'left' }}>
                  <span className={`source-tag ${cat.category}`}>{CATEGORY_KR[cat.category] || cat.category}</span>
                </span>
                <div className="crawl-year-bar-container">
                  <div className={`crawl-year-bar-segment source-${cat.category === 'newsapi' ? 'news' : cat.category === 'gnews' ? 'gdelt' : 'nyt'}`} style={{ width: `${(cat.count / maxCatCount * 100)}%` }} />
                </div>
                <span className="crawl-year-count">{cat.count.toLocaleString()}</span>
              </div>
            ))}
          </div>
          <h3 className="section-title" style={{ marginTop: '32px' }}>소스별 분류율</h3>
          <div className="admin-table-wrapper">
            <table className="admin-table">
              <thead><tr><th>Source</th><th>전체</th><th>분류완료</th><th>분류율</th><th>Progress</th></tr></thead>
              <tbody>{clsStats.source_classification.map(s => (
                <tr key={s.data_source}>
                  <td><SourceTag source={s.data_source || 'unknown'} /></td><td>{s.total.toLocaleString()}</td><td>{s.classified.toLocaleString()}</td><td>{s.classification_rate}%</td>
                  <td style={{ width: '30%' }}><div className="rate-limit-bar" style={{ height: 6 }}><div className={`rate-limit-fill ${s.classification_rate > 80 ? 'safe' : 'warning'}`} style={{ width: `${s.classification_rate}%` }} /></div></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      )}

      {/* ═══ TAB 2: 기사 관리 ═══ */}
      {subTab === 'articles' && (
        <div className="crawl-control-panel">
          <div className="filters-bar" style={{ justifyContent: 'space-between', marginBottom: '20px' }}>
            <div className="data-tabs" style={{ margin: 0 }}>
              {[
                { id: 'all', label: '전체', count: clsStats?.total },
                { id: 'classified', label: '✓ 분류완료', count: clsStats?.classified },
                { id: 'pending', label: '⏳ 대기', count: clsStats?.unclassified },
                { id: 'failed', label: '✕ 에러', count: clsStats?.failed },
              ].map(f => (
                <button key={f.id} className={`data-tab ${articleFilter === f.id ? 'active' : ''}`} onClick={() => handleFilterChange(f.id)}>
                  {f.label}{f.count != null ? <span style={{ marginLeft: 6, opacity: 0.6 }}>{f.count.toLocaleString()}</span> : ''}
                </button>
              ))}
            </div>
            {selectedIds.size > 0 ? (
              <div className="crawl-message" style={{ display: 'flex', gap: 12, alignItems: 'center', background: 'rgba(255, 107, 53, 0.1)', borderColor: 'rgba(255, 107, 53, 0.2)', color: '#FF6B35' }}>
                <span style={{ fontWeight: 600 }}>{selectedIds.size}건 선택됨</span>
                <button className="action-btn small primary" onClick={() => handleRetry(Array.from(selectedIds))}>🔄 재시도</button>
                <button className="action-btn small" onClick={() => handleDelete()} style={{ background: 'rgba(255, 60, 60, 0.15)', color: '#FF5C5C', border: '1px solid rgba(255, 60, 60, 0.3)' }}>🗑 삭제</button>
                <button onClick={() => setSelectedIds(new Set())} style={{ background: 'transparent', border: 'none', color: '#FF6B35', cursor: 'pointer', fontSize: '1.2em', padding: '0 4px' }}>×</button>
              </div>
            ) : (
              <span className="pagination-info">행을 클릭하면 상세 정보, 체크박스로 일괄 작업 가능</span>
            )}
          </div>
          <div className="admin-table-wrapper">
            <table className="admin-table">
              <thead><tr>
                <th style={{ width: 30 }}><input type="checkbox" checked={selectedIds.size === articles.length && articles.length > 0} onChange={toggleSelectAll} /></th>
                <th>기사 (원본)</th><th>소스</th><th>상태</th><th>AI 카테고리</th><th>스코어</th><th>W/B/D</th>
              </tr></thead>
              <tbody>
                {articles.length === 0 ? <tr><td colSpan={7} style={{ textAlign: 'center', padding: 30 }}>
                  <div style={{ color: '#888' }}>{ articleFilter === 'failed' ? '✓ 에러 상태의 기사가 없습니다.' : articleFilter === 'pending' ? '✓ 분류 대기 중인 기사가 없습니다.' : '데이터가 없습니다.' }</div>
                </td></tr> : articles.map(a => {
                  const isExp = expandedArticleId === a.id;
                  const sIcon = a.is_classified === 1 ? '✓' : a.is_classified === -1 ? '✕' : '⏳';
                  const sColor = a.is_classified === 1 ? 'var(--color-success)' : a.is_classified === -1 ? 'var(--color-danger)' : 'var(--color-warning)';
                  return (
                    <React.Fragment key={a.id}>
                      <tr style={{ cursor: 'pointer' }} onClick={() => setExpandedArticleId(isExp ? null : a.id)}>
                        <td onClick={e => e.stopPropagation()}><input type="checkbox" checked={selectedIds.has(a.id)} onChange={() => toggleSelect(a.id)} /></td>
                        <td style={{ maxWidth: 320 }}>
                          <div style={{ fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={a.title}>{a.ai_translated_title || a.title}</div>
                          <div style={{ fontSize: '0.8em', color: '#777' }}>{formatDate(a.published_at)}</div>
                        </td>
                        <td><SourceTag source={a.data_source || 'unknown'} /></td>
                        <td><span style={{ color: sColor, fontWeight: 600 }}>{sIcon}</span></td>
                        <td>{a.ai_category ? <span className={`source-tag ${a.ai_category}`}>{CATEGORY_KR[a.ai_category] || a.ai_category}</span> : <span style={{ color: '#555' }}>-</span>}</td>
                        <td>{a.ai_impact_score != null ? <span style={{ color: a.ai_impact_score > 0 ? 'var(--color-success)' : a.ai_impact_score < 0 ? 'var(--color-danger)' : 'inherit', fontWeight: 600 }}>{a.ai_impact_score > 0 ? '+' : ''}{a.ai_impact_score}</span> : '-'}</td>
                        <td style={{ fontSize: '0.85em', whiteSpace: 'nowrap' }}>{a.ai_wti != null ? `${a.ai_wti}/${a.ai_brent}/${a.ai_dubai}` : '-'}</td>
                      </tr>
                      {isExp && (
                        <tr><td colSpan={7} style={{ padding: 0, background: 'var(--color-bg-secondary, #1a1d23)' }}>
                          <div style={{ padding: '12px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, fontSize: '0.88em' }}>
                            <div>
                              <div style={{ fontWeight: 700, marginBottom: 8, color: 'var(--color-text-muted)' }}>📥 원본 데이터 (Input)</div>
                              <div style={{ lineHeight: 1.7 }}>
                                <div><strong>ID:</strong> <span style={{ fontFamily: 'monospace', fontSize: '0.85em' }}>{a.id.slice(0,16)}...</span></div>
                                <div><strong>제목:</strong> {a.title}</div>
                                <div><strong>설명:</strong> <span style={{ color: '#999' }}>{a.description || '없음'}</span></div>
                                <div><strong>소스:</strong> {a.source_name} ({a.data_source})</div>
                                <div><strong>발행일:</strong> {formatDate(a.published_at)} · <strong>수집일:</strong> {formatDate(a.collected_at)}</div>
                                <div><strong>URL:</strong> <a href={a.url} target="_blank" rel="noreferrer" style={{ color: '#4a9eff' }}>원문 링크 ↗</a></div>
                                <div><strong>재시도:</strong> {a.retry_count}회</div>
                              </div>
                            </div>
                            <div>
                              <div style={{ fontWeight: 700, marginBottom: 8, color: 'var(--color-text-muted)' }}>🤖 AI 분석 결과 (Output)</div>
                              {a.is_classified === 1 ? (
                                <div style={{ lineHeight: 1.7 }}>
                                  <div><strong>번역:</strong> {a.ai_translated_title || '-'}</div>
                                  <div><strong>카테고리:</strong> {CATEGORY_KR[a.ai_category || ''] || a.ai_category} ({a.ai_sub_categories?.join(', ') || '-'})</div>
                                  <div><strong>유가 관련:</strong> {a.ai_is_relevant ? '✓' : '✕'} · 신뢰도 {((a.ai_confidence || 0) * 100).toFixed(0)}%</div>
                                  <div><strong>임팩트:</strong> <span style={{ color: (a.ai_impact_score || 0) > 0 ? 'var(--color-success)' : 'var(--color-danger)' }}>{(a.ai_impact_score || 0) > 0 ? '+' : ''}{a.ai_impact_score}</span> (W:{a.ai_wti} B:{a.ai_brent} D:{a.ai_dubai})</div>
                                  <div><strong>분석 시각:</strong> {a.ai_classified_at ? formatDate(a.ai_classified_at) : '-'}</div>
                                  <div style={{ marginTop: 4 }}><strong>AI 요약:</strong> <span style={{ color: '#bbb' }}>{a.ai_summary || '없음'}</span></div>
                                </div>
                              ) : a.is_classified === -1 ? (
                                <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 6, padding: 10, color: 'var(--color-danger)' }}>
                                  <strong>에러:</strong> {a.classification_error || 'Unknown'}
                                </div>
                              ) : <div style={{ color: '#888' }}>아직 AI 분석이 수행되지 않았습니다.</div>}
                              <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
                                <button className="action-btn small primary" onClick={e => { e.stopPropagation(); handleRetry([a.id]); }}>🔄 재시도</button>
                                <button className="action-btn small" onClick={e => { e.stopPropagation(); handleDelete([a.id]); }} style={{ background: 'rgba(255, 60, 60, 0.1)', color: '#FF5C5C', border: '1px solid rgba(255, 60, 60, 0.3)' }}>🗑 삭제</button>
                              </div>
                            </div>
                          </div>
                        </td></tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
          {articlesTotal > PAGE_SIZE && (
            <div className="pagination-bar" style={{ marginTop: '16px', borderTop: 'none' }}>
              <span className="pagination-info">전체 {articlesTotal.toLocaleString()}건 중 {articlePage * PAGE_SIZE + 1}-{Math.min((articlePage + 1) * PAGE_SIZE, articlesTotal)}건</span>
              <div className="pagination-buttons">
                <button className="pagination-btn" disabled={articlePage === 0} onClick={() => handlePageChange(articlePage - 1)}>← 이전</button>
                <button className="pagination-btn" disabled={(articlePage + 1) * PAGE_SIZE >= articlesTotal} onClick={() => handlePageChange(articlePage + 1)}>다음 →</button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══ TAB 3: 작업 이력 ═══ */}
      {subTab === 'jobs' && (
        <div className="crawl-control-panel">
          <div className="crawl-control-header">
            <div className="crawl-status-indicator">
              <span className="crawl-status-text">배치 작업 이력</span>
            </div>
          </div>
          <div className="admin-table-wrapper">
          <table className="admin-table">
            <thead><tr><th>Job ID</th><th>상태</th><th>대상</th><th>성공/실패</th><th>소요</th><th>생성</th><th>완료</th><th></th></tr></thead>
            <tbody>
              {jobs.length === 0 ? <tr><td colSpan={8} style={{ textAlign: 'center', padding: 20 }}>작업 이력이 없습니다.</td></tr> : jobs.map(job => {
                const isExp = expandedJobId === job.id;
                const sColor = job.status === 'completed' ? 'var(--color-success)' : job.status === 'running' ? '#4a9eff' : job.status === 'failed' ? 'var(--color-danger)' : 'var(--color-warning)';
                const sLabel = job.status === 'completed' ? '✓ 완료' : job.status === 'running' ? '⟳ 실행 중' : job.status === 'failed' ? '✕ 실패' : '⏳ 대기';
                const dur = job.duration_ms != null ? (job.duration_ms > 60000 ? `${(job.duration_ms/60000).toFixed(1)}분` : `${(job.duration_ms/1000).toFixed(1)}초`) : '-';
                return (
                  <React.Fragment key={job.id}>
                    <tr style={{ cursor: 'pointer' }} onClick={() => setExpandedJobId(isExp ? null : job.id)}>
                      <td style={{ fontFamily: 'monospace', fontSize: '0.85em' }}>{job.id}</td>
                      <td><span style={{ color: sColor, fontWeight: 600 }}>{sLabel}</span></td>
                      <td>{job.total_articles}건</td>
                      <td>{job.status === 'queued' || job.status === 'running' ? '처리 중...' : <><span style={{ color: 'var(--color-success)' }}>{job.success_count}</span> / <span style={{ color: 'var(--color-danger)' }}>{job.fail_count}</span></>}</td>
                      <td>{dur}</td>
                      <td>{formatDate(job.created_at)}</td>
                      <td>{job.completed_at ? formatDate(job.completed_at) : '-'}</td>
                      <td>{isExp ? '▲' : '▼'}</td>
                    </tr>
                    {isExp && (
                      <tr><td colSpan={8} style={{ padding: 0, background: 'var(--color-bg-secondary, #1a1d23)' }}>
                        <div style={{ padding: '12px 16px' }}>
                          {job.error_message && <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 6, padding: '8px 12px', marginBottom: 12, color: 'var(--color-danger)', fontSize: '0.9em' }}><strong>에러:</strong> {job.error_message}</div>}
                          {job.results_detail ? (
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                              <div>
                                <div style={{ fontWeight: 600, marginBottom: 6, color: 'var(--color-success)' }}>✓ 성공 ({job.results_detail.success_ids?.length || 0}건)</div>
                                <div style={{ maxHeight: 120, overflowY: 'auto', fontSize: '0.85em' }}>
                                  {(job.results_detail.success_ids || []).map(id => { const snap = job.results_detail?.before_snapshot?.[id]; return <div key={id} style={{ padding: '3px 6px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}><span style={{ color: '#aaa' }}>{snap?.title || id.slice(0,12)}</span></div>; })}
                                  {(!job.results_detail.success_ids?.length) && <div style={{ color: '#666' }}>없음</div>}
                                </div>
                              </div>
                              <div>
                                <div style={{ fontWeight: 600, marginBottom: 6, color: 'var(--color-danger)' }}>✕ 실패 ({job.results_detail.failed?.length || 0}건)</div>
                                <div style={{ maxHeight: 120, overflowY: 'auto', fontSize: '0.85em' }}>
                                  {(job.results_detail.failed || []).map(f => <div key={f.id} style={{ padding: '3px 6px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}><div style={{ color: '#aaa' }}>{f.title}</div><div style={{ color: 'var(--color-danger)', fontSize: '0.85em' }}>{f.error}</div></div>)}
                                  {(!job.results_detail.failed?.length) && <div style={{ color: '#666' }}>없음</div>}
                                </div>
                              </div>
                            </div>
                          ) : (job.status === 'queued' || job.status === 'running') ? <div style={{ color: '#4a9eff' }}>⟳ 진행 중... 자동 새로고침됩니다.</div> : <div style={{ color: '#888' }}>세부 결과 없음</div>}
                        </div>
                      </td></tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      )}
    </>
  );
};

export default PipelineSectionV2;
