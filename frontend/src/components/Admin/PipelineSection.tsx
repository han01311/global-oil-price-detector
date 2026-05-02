import React, { useState, useEffect, useRef } from 'react';
import {
  fetchClassificationStats,
  fetchPipelineArticles,
  deletePipelineArticles,
  retryPipelineItems,
  archivePipelineArticles,
  fetchPipelineJobs,
} from '../../services/adminApi';
import type {
  ClassificationStats, PipelineArticle, PipelineJob
} from '../../services/adminApi';

export const CATEGORY_KR: Record<string, string> = {
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
  const [subTab, setSubTab] = useState<PipelineTab>('articles');

  const [clsStats, setClsStats] = useState<ClassificationStats | null>(null);
  const [articles, setArticles] = useState<PipelineArticle[]>([]);
  const [articlesTotal, setArticlesTotal] = useState(0);
  const [articleFilter, setArticleFilter] = useState(() => localStorage.getItem('pipelineArticleFilter') || 'all');
  const [articleCategory, setArticleCategory] = useState(() => localStorage.getItem('pipelineCategoryFilter') || '');
  const [articleKeyword, setArticleKeyword] = useState('');
  const [articlePage, setArticlePage] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [expandedArticleId, setExpandedArticleId] = useState<string | null>(null);
  
  const [recoverArticleId, setRecoverArticleId] = useState<string | null>(null);
  const [recoverText, setRecoverText] = useState("");
  const [recoverLoading, setRecoverLoading] = useState(false);
  const [viewedArticles, setViewedArticles] = useState<Set<string>>(() => {
    try { return new Set(JSON.parse(localStorage.getItem('viewedArticles') || '[]')); } catch { return new Set(); }
  });

  const markAsViewed = (id: string) => {
    setViewedArticles(prev => {
      if (prev.has(id)) return prev;
      const next = new Set(prev);
      next.add(id);
      localStorage.setItem('viewedArticles', JSON.stringify(Array.from(next)));
      return next;
    });
  };

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
  const loadArticles = async (filter = articleFilter, page = articlePage, keyword = articleKeyword, cat = articleCategory) => {
    const res = await fetchPipelineArticles(filter, PAGE_SIZE, page * PAGE_SIZE, keyword, cat || undefined);
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
  const handleArchive = async (ids?: string[]) => {
    const targets = ids || Array.from(selectedIds);
    if (targets.length === 0) return;
    if (!confirm(`선택한 ${targets.length}건의 기사를 중복방지 보관함으로 이동하시겠습니까?\n이후 일반 목록에서는 보이지 않게 됩니다.`)) return;
    try {
      const res = await archivePipelineArticles(targets);
      showToast(`${res.archived}건 보관 처리 완료`);
      setSelectedIds(new Set()); setExpandedArticleId(null);
      await loadArticles(); await loadStats();
    } catch { showToast('보관 처리에 실패했습니다.', 'err'); }
  };
  const toggleSelect = (id: string) => setSelectedIds(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const toggleSelectAll = () => selectedIds.size === articles.length ? setSelectedIds(new Set()) : setSelectedIds(new Set(articles.map(a => a.id)));
  const handleFilterChange = async (f: string) => { localStorage.setItem('pipelineArticleFilter', f); setArticleFilter(f); setArticlePage(0); setSelectedIds(new Set()); setExpandedArticleId(null); await loadArticles(f, 0, articleKeyword, articleCategory); };
  const handleCategoryChange = async (cat: string) => { localStorage.setItem('pipelineCategoryFilter', cat); setArticleCategory(cat); setArticlePage(0); setSelectedIds(new Set()); setExpandedArticleId(null); await loadArticles(articleFilter, 0, articleKeyword, cat); };
  const handlePageChange = async (p: number) => { setArticlePage(p); setSelectedIds(new Set()); setExpandedArticleId(null); await loadArticles(articleFilter, p, articleKeyword, articleCategory); };
  const handleSearchSubmit = async () => { setArticlePage(0); setSelectedIds(new Set()); setExpandedArticleId(null); await loadArticles(articleFilter, 0, articleKeyword, articleCategory); };

  useEffect(() => {
    // When subTab becomes articles, pick up any filter passed via localStorage
    if (subTab === 'articles') {
      const storedFilter = localStorage.getItem('pipelineArticleFilter');
      const storedCategory = localStorage.getItem('pipelineCategoryFilter') || '';
      if ((storedFilter && storedFilter !== articleFilter) || storedCategory !== articleCategory) {
        if (storedFilter) setArticleFilter(storedFilter);
        setArticleCategory(storedCategory);
        setArticlePage(0);
        setSelectedIds(new Set());
        setExpandedArticleId(null);
        loadArticles(storedFilter || articleFilter, 0, articleKeyword, storedCategory);
      }
    }
  }, [subTab]);

  const handleRecoverSubmit = async () => {
    if (!recoverArticleId || !recoverText.trim()) return;
    setRecoverLoading(true);
    try {
      const { recoverArticle } = await import('../../services/adminApi');
      await recoverArticle(recoverArticleId, recoverText);
      showToast(`원문 저장 완료! 해당 기사는 AI 분석 대기열(미분류)로 이동되었습니다.`);
      setRecoverArticleId(null);
      setRecoverText('');
      await loadArticles();
      await loadStats();
    } catch (e) {
      showToast(`복구 실패: ${e}`, 'err');
    }
    setRecoverLoading(false);
  };

  if (loading) return (
    <div className="overview-grid">
      {[...Array(4)].map((_, i) => <div key={i} className="overview-card"><div className="admin-skeleton" style={{ width: '60%', height: 14, marginBottom: 10 }} /><div className="admin-skeleton" style={{ width: '40%', height: 32 }} /></div>)}
    </div>
  );

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

      {/* ═══ TAB 1: 기사 관리 ═══ */}
      {subTab === 'articles' && (
        <div className="crawl-control-panel">
          <div className="filters-bar" style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
              <div className="data-tabs" style={{ margin: 0 }}>
                {[
                  { id: 'all', label: '전체', count: clsStats?.total },
                  { id: 'classified', label: '✓ 분류완료', count: clsStats?.classified },
                  { id: 'irrelevant', label: '관련성 없음', count: clsStats?.irrelevant },
                  { id: 'pending', label: '⏳ 미분류', count: clsStats?.unclassified },
                  { id: 'failed', label: '✕ 에러', count: clsStats?.failed },
                  { id: 'archived', label: '🚫 중복방지 보관함', count: clsStats?.archived },
                ].map(f => (
                  <button key={f.id} className={`data-tab ${articleFilter === f.id ? 'active' : ''}`} onClick={() => handleFilterChange(f.id)}>
                    {f.label}{f.count != null ? <span style={{ marginLeft: 6, opacity: 0.6 }}>{f.count.toLocaleString()}</span> : ''}
                  </button>
                ))}
              </div>
              {selectedIds.size > 0 ? (
                <div className="crawl-message" style={{ display: 'flex', gap: 12, alignItems: 'center', background: 'rgba(255, 107, 53, 0.1)', borderColor: 'rgba(255, 107, 53, 0.2)', color: '#FF6B35', padding: '6px 12px', borderRadius: '6px' }}>
                  <span style={{ fontWeight: 600 }}>{selectedIds.size}건 선택됨</span>
                  <button className="action-btn small primary" onClick={() => handleRetry(Array.from(selectedIds))}>🔄 재시도</button>
                  <button className="action-btn small" onClick={() => handleArchive()} style={{ background: 'rgba(255, 255, 255, 0.1)', color: '#fff', border: '1px solid rgba(255, 255, 255, 0.2)' }}>🚫 보관</button>
                  <button className="action-btn small" onClick={() => handleDelete()} style={{ background: 'rgba(255, 60, 60, 0.15)', color: '#FF5C5C', border: '1px solid rgba(255, 60, 60, 0.3)' }}>🗑 삭제</button>
                  <button onClick={() => setSelectedIds(new Set())} style={{ background: 'transparent', border: 'none', color: '#FF6B35', cursor: 'pointer', fontSize: '1.2em', padding: '0 4px' }}>×</button>
                </div>
              ) : (
                <span className="pagination-info">행을 클릭하면 상세 정보, 체크박스로 일괄 작업 가능</span>
              )}
            </div>
            <div style={{ 
              display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap', 
              background: 'rgba(255, 255, 255, 0.02)', padding: '14px 18px', borderRadius: '12px', 
              border: '1px solid rgba(255,255,255,0.08)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '1rem', opacity: 0.7 }}>📁</span>
                <select
                  className="filter-select"
                  value={articleCategory}
                  onChange={e => handleCategoryChange(e.target.value)}
                  style={{ width: '180px', fontWeight: 500, cursor: 'pointer', padding: '8px 12px' }}
                >
                  <option value="">전체 카테고리</option>
                  <option value="geopolitics">지정학 (Geopolitics)</option>
                  <option value="supply">공급 (Supply)</option>
                  <option value="demand">수요 (Demand)</option>
                  <option value="macro">거시경제 (Macro)</option>
                  <option value="climate">기후/ESG (Climate)</option>
                  <option value="speculation">투기/심리 (Speculation)</option>
                  <option value="uncategorized">⚠️ 미지정 (문제있음)</option>
                </select>
              </div>
              
              <div style={{ width: '1px', height: '24px', background: 'rgba(255,255,255,0.1)', margin: '0 4px' }} />
              
              <div style={{ 
                flex: 1, display: 'flex', alignItems: 'center', maxWidth: '500px', 
                background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.1)', 
                borderRadius: '8px', overflow: 'hidden', transition: 'border-color 0.2s' 
              }}>
                <span style={{ padding: '0 12px', fontSize: '0.9em', opacity: 0.5 }}>🔍</span>
                <input 
                  type="text" 
                  value={articleKeyword} 
                  onChange={e => setArticleKeyword(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSearchSubmit()}
                  placeholder="기사 제목, 요약, 또는 키워드로 검색..." 
                  style={{ flex: 1, background: 'transparent', border: 'none', color: '#e4e8ef', outline: 'none', padding: '10px 0', fontSize: '0.85rem' }} 
                />
                <button 
                  className="action-btn small primary" 
                  onClick={handleSearchSubmit} 
                  style={{ margin: '4px', padding: '6px 16px', borderRadius: '6px', fontWeight: 600 }}
                >
                  검색
                </button>
              </div>
            </div>
          </div>
          <div className="admin-table-wrapper">
            <table className="admin-table">
              <thead><tr>
                <th style={{ width: 30 }}><input type="checkbox" checked={selectedIds.size === articles.length && articles.length > 0} onChange={toggleSelectAll} /></th>
                <th>기사 (원본)</th><th>소스</th><th>상태</th><th>AI 카테고리</th><th>스코어</th><th>W/B/D</th>
              </tr></thead>
              <tbody>
                {articles.length === 0 ? <tr><td colSpan={7} style={{ textAlign: 'center', padding: 30 }}>
                  <div style={{ color: '#888' }}>{ articleFilter === 'failed' ? '✓ 에러 상태의 기사가 없습니다.' : articleFilter === 'pending' ? '✓ 미분류 상태의 기사가 없습니다.' : '데이터가 없습니다.' }</div>
                </td></tr> : articles.map(a => {
                  const isExp = expandedArticleId === a.id;
                  const isNew = !viewedArticles.has(a.id) && (
                    (a.is_classified === 0 && a.collected_at && (new Date().getTime() - new Date(a.collected_at).getTime() < 24 * 60 * 60 * 1000)) ||
                    (a.is_classified === 1 && a.ai_classified_at && (new Date().getTime() - new Date(a.ai_classified_at).getTime() < 24 * 60 * 60 * 1000))
                  );
                  const sIcon = a.is_classified === 1 ? '✓' : a.is_classified === -1 ? '✕' : a.is_classified === -2 ? '관련없음' : a.is_classified === -3 ? '보관됨' : '⏳';
                  const sColor = a.is_classified === 1 ? 'var(--color-success)' : a.is_classified === -1 ? 'var(--color-danger)' : (a.is_classified === -2 || a.is_classified === -3) ? '#888' : 'var(--color-warning)';
                  return (
                    <React.Fragment key={a.id}>
                      <tr style={{ cursor: 'pointer' }} onClick={() => { setExpandedArticleId(isExp ? null : a.id); markAsViewed(a.id); }}>
                        <td onClick={e => e.stopPropagation()}><input type="checkbox" checked={selectedIds.has(a.id)} onChange={() => toggleSelect(a.id)} /></td>
                        <td style={{ maxWidth: 320 }}>
                          <div style={{ fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={a.title}>
                            {isNew && <span style={{ background: '#FF4D4D', color: '#fff', fontSize: '10px', padding: '2px 6px', borderRadius: '4px', marginRight: '6px', fontWeight: 'bold' }}>NEW</span>}
                            {a.ai_translated_title || a.title}
                          </div>
                          <div style={{ fontSize: '0.8em', color: '#777' }}>{formatDate(a.published_at)}</div>
                        </td>
                        <td><SourceTag source={a.data_source || 'unknown'} /></td>
                        <td><span style={{ color: sColor, fontWeight: 600 }}>{sIcon}</span></td>
                        <td>{a.ai_category ? <span className={`source-tag ${a.ai_category}`}>{CATEGORY_KR[a.ai_category] || a.ai_category}</span> : <span style={{ color: '#555' }}>-</span>}</td>
                        <td>{a.ai_impact_score != null ? <span style={{ color: a.ai_impact_score > 0 ? 'var(--color-success)' : a.ai_impact_score < 0 ? 'var(--color-danger)' : 'inherit', fontWeight: 600 }}>{a.ai_impact_score > 0 ? '+' : ''}{a.ai_impact_score}</span> : '-'}</td>
                        <td style={{ fontSize: '0.85em', whiteSpace: 'nowrap' }}>{a.ai_wti != null ? `${a.ai_wti}/${a.ai_brent}/${a.ai_dubai}` : '-'}</td>
                      </tr>
                      {isExp && (
                        <tr><td colSpan={7} style={{ padding: 0, borderBottom: '1px solid rgba(255,255,255,0.05)', whiteSpace: 'normal' }}>
                          <div style={{ padding: '20px', display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: '20px', background: 'rgba(0, 0, 0, 0.2)' }}>
                            {/* Input Column */}
                            <div style={{ background: 'rgba(255, 255, 255, 0.03)', borderRadius: '12px', padding: '16px', border: '1px solid rgba(255, 255, 255, 0.05)', minWidth: 0 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '12px' }}>
                                <span style={{ fontSize: '1.2em' }}>📥</span>
                                <span style={{ fontWeight: 700, color: '#fff', fontSize: '1.05em' }}>원본 데이터 (Input)</span>
                              </div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.9em' }}>
                                <div style={{ display: 'flex' }}><span style={{ color: '#888', marginRight: '8px', minWidth: '60px' }}>원문 제목</span><span style={{ color: '#fff', fontWeight: 500, wordBreak: 'break-word' }}>{a.title}</span></div>
                                <div><span style={{ color: '#888', marginRight: '8px', width: '60px', display: 'inline-block' }}>기사 설명</span><div style={{ background: 'rgba(0,0,0,0.3)', padding: '10px', borderRadius: '6px', color: '#bbb', marginTop: '6px', lineHeight: 1.5, wordBreak: 'break-word' }}>{a.description || '제공된 설명이 없습니다.'}</div></div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
                                  <div><span style={{ color: '#888', marginRight: '8px' }}>데이터 소스</span><span style={{ color: '#fff' }}>{a.source_name} ({a.data_source})</span></div>
                                  <div><span style={{ color: '#888', marginRight: '8px' }}>발행일</span><span style={{ color: '#fff' }}>{formatDate(a.published_at)}</span></div>
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                  <div style={{ display: 'flex', minWidth: 0, overflow: 'hidden' }}><span style={{ color: '#888', marginRight: '8px', whiteSpace: 'nowrap' }}>원문 링크</span><a href={a.url} target="_blank" rel="noreferrer" style={{ color: '#4a9eff', textDecoration: 'none', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>새 탭에서 열기 ↗</a></div>
                                  <div style={{ whiteSpace: 'nowrap' }}><span style={{ color: '#888', marginRight: '8px' }}>수집일</span><span style={{ color: '#fff' }}>{formatDate(a.collected_at)}</span></div>
                                </div>
                                <div style={{ marginTop: '12px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.1)', padding: '12px', borderRadius: '8px' }}>
                                  {(!a.description || a.description.length < 30) ? (
                                    <>
                                      <div style={{ color: '#ffb84d', fontWeight: 600, fontSize: '0.95em', marginBottom: '8px' }}>⚠️ 본문 텍스트 추출 실패 또는 부족</div>
                                      <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: '0.9em', marginBottom: '12px' }}>원본 페이지에서 텍스트를 복사하여 아래에 붙여넣으면 AI가 자동 정리합니다.</div>
                                    </>
                                  ) : (
                                    <>
                                      <div style={{ color: '#00d4ff', fontWeight: 600, fontSize: '0.95em', marginBottom: '8px' }}>✏️ 본문 수정 (수동 덮어쓰기)</div>
                                      <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: '0.9em', marginBottom: '12px' }}>본문 내용이 부정확하거나 덜 추출된 경우 직접 텍스트를 입력하여 업데이트할 수 있습니다.</div>
                                    </>
                                  )}

                                  {recoverArticleId === a.id ? (
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                      <textarea
                                        value={recoverText}
                                        onChange={e => setRecoverText(e.target.value)}
                                        placeholder="기사 본문을 여기에 붙여넣으세요..."
                                        style={{ width: '100%', height: '120px', background: 'rgba(0,0,0,0.4)', color: '#fff', border: '1px solid rgba(255,255,255,0.2)', borderRadius: '6px', padding: '10px', fontSize: '0.9em', resize: 'vertical' }}
                                      />
                                      <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                                        <button className="action-btn small" onClick={() => { setRecoverArticleId(null); setRecoverText(''); }} style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.2)' }}>취소</button>
                                        <button className="action-btn small primary" onClick={handleRecoverSubmit} disabled={recoverLoading}>
                                          {recoverLoading ? '⏳ 복구 중...' : '✨ AI 자동 정리 및 업데이트'}
                                        </button>
                                      </div>
                                    </div>
                                  ) : (
                                    <button className="action-btn small" onClick={() => setRecoverArticleId(a.id)} style={{ background: 'rgba(255,255,255,0.1)', color: '#fff', border: '1px solid rgba(255,255,255,0.2)' }}>📝 텍스트 직접 입력하여 수정</button>
                                  )}
                                </div>
                              </div>
                            </div>

                            {/* Output Column */}
                            <div style={{ background: 'rgba(255, 255, 255, 0.03)', borderRadius: '12px', padding: '16px', border: '1px solid rgba(255, 255, 255, 0.05)', display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '12px' }}>
                                <span style={{ fontSize: '1.2em' }}>🤖</span>
                                <span style={{ fontWeight: 700, color: '#fff', fontSize: '1.05em' }}>AI 분석 결과 (Output)</span>
                                {a.is_classified === -2 && <span className="issue-badge" style={{ marginLeft: 'auto', background: 'rgba(255, 255, 255, 0.1)', color: '#bbb' }}>관련성 없음</span>}
                                {a.is_classified === -3 && <span className="issue-badge" style={{ marginLeft: 'auto', background: 'rgba(255, 107, 53, 0.2)', color: '#FF6B35' }}>중복방지 (보관됨)</span>}
                              </div>
                              
                              <div style={{ flex: 1 }}>
                                {a.is_classified === 1 || a.is_classified === -2 || a.is_classified === -3 ? (
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.9em' }}>
                                    <div style={{ display: 'flex' }}><span style={{ color: '#888', marginRight: '8px', minWidth: '60px' }}>번역 제목</span><span style={{ color: '#00d4ff', fontWeight: 500, wordBreak: 'break-word' }}>{a.ai_translated_title || '-'}</span></div>
                                    <div style={{ display: 'flex', gap: '20px' }}>
                                      <div><span style={{ color: '#888', marginRight: '8px' }}>카테고리</span><span className={`source-tag ${a.ai_category}`} style={{ display: 'inline-block', padding: '2px 8px' }}>{CATEGORY_KR[a.ai_category || ''] || a.ai_category}</span></div>
                                      <div><span style={{ color: '#888', marginRight: '8px' }}>서브 분류</span><span style={{ color: '#fff' }}>{a.ai_sub_categories?.join(', ') || '-'}</span></div>
                                    </div>
                                    <div style={{ display: 'flex', gap: '20px', marginTop: '4px' }}>
                                      <div><span style={{ color: '#888', marginRight: '8px' }}>유가 영향</span><span style={{ color: (a.ai_impact_score || 0) > 0 ? 'var(--color-success)' : (a.ai_impact_score || 0) < 0 ? 'var(--color-danger)' : '#fff', fontWeight: 'bold', fontSize: '1.1em' }}>{(a.ai_impact_score || 0) > 0 ? '+' : ''}{a.ai_impact_score}</span></div>
                                      <div><span style={{ color: '#888', marginRight: '8px' }}>신뢰도</span><span style={{ color: '#fff' }}>{((a.ai_confidence || 0) * 100).toFixed(0)}%</span></div>
                                      <div><span style={{ color: '#888', marginRight: '8px' }}>유종별</span><span style={{ color: '#bbb', fontFamily: 'monospace' }}>W:{a.ai_wti} B:{a.ai_brent} D:{a.ai_dubai}</span></div>
                                    </div>
                                    <div>
                                      <span style={{ color: '#888', marginRight: '8px', display: 'block', marginBottom: '6px' }}>AI 종합 의견</span>
                                      <div style={{ background: 'rgba(0, 212, 255, 0.05)', borderLeft: '3px solid #00d4ff', padding: '10px 12px', borderRadius: '0 6px 6px 0', color: '#e2e8f0', lineHeight: 1.6, wordBreak: 'break-word' }}>
                                        {a.ai_summary || '요약 내용이 없습니다.'}
                                      </div>
                                    </div>
                                  </div>
                                ) : a.is_classified === -1 ? (
                                  <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '8px', padding: '16px', color: 'var(--color-danger)', lineHeight: 1.5 }}>
                                    <div style={{ fontWeight: 600, marginBottom: '8px' }}>⚠️ 분석 중 오류가 발생했습니다</div>
                                    <div style={{ fontSize: '0.9em', color: '#ffb3b3' }}>{a.classification_error || 'Unknown Error'}</div>
                                  </div>
                                ) : (
                                  <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', color: '#666', border: '1px dashed rgba(255,255,255,0.1)', borderRadius: '8px' }}>
                                    아직 AI 분석이 수행되지 않았습니다.
                                  </div>
                                )}
                              </div>

                              <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.1)', display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                                <button className="action-btn small primary" onClick={e => { e.stopPropagation(); handleRetry([a.id]); }} style={{ padding: '6px 12px' }}>🔄 재시도</button>
                                {a.is_classified !== -3 && <button className="action-btn small" onClick={e => { e.stopPropagation(); handleArchive([a.id]); }} style={{ background: 'rgba(255, 255, 255, 0.1)', color: '#fff', border: '1px solid rgba(255, 255, 255, 0.2)', padding: '6px 12px' }}>🚫 보관</button>}
                                <button className="action-btn small" onClick={e => { e.stopPropagation(); handleDelete([a.id]); }} style={{ background: 'rgba(255, 60, 60, 0.1)', color: '#FF5C5C', border: '1px solid rgba(255, 60, 60, 0.3)', padding: '6px 12px' }}>🗑 삭제</button>
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
