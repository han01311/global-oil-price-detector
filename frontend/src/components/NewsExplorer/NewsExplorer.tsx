import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { Card } from '../common/Card';
import { useNewsData } from '../../hooks/useNewsData';
import { NewsCard } from './NewsCard';
import { Skeleton } from '../common/Skeleton';
import { Badge } from '../common/Badge';
import { EmptyState } from '../common/EmptyState';
import { useDashboardContext } from '../../context/DashboardContext';
import { fetchNewsByDate } from '../../services/api';
import type { DBNewsArticle } from '../../services/api';
import './NewsExplorer.css';

type SortOrder = 'time' | 'impact';
type Category = 'All' | 'geopolitics' | 'supply' | 'demand' | 'macro' | 'climate' | 'speculation';
type CrudeType = 'All' | 'dubai' | 'brent' | 'wti';

const CATEGORIES: Category[] = ['All', 'geopolitics', 'supply', 'demand', 'macro', 'climate', 'speculation'];
const CRUDE_TYPES: CrudeType[] = ['All', 'dubai', 'brent', 'wti'];

export const NewsExplorer: React.FC = () => {
  const { articles, loading, error, refetch } = useNewsData();
  const { selectedDate, setSelectedDate, setHighlightedCategory } = useDashboardContext();
  const [activeCategory, setActiveCategory] = useState<Category>('All');
  const [activeCrudeType, setActiveCrudeType] = useState<CrudeType>('All');
  const [sortOrder, setSortOrder] = useState<SortOrder>('time');

  // DB 기사 (차트 날짜 클릭 시 로드)
  const [dbArticles, setDbArticles] = useState<DBNewsArticle[]>([]);
  const [dbLoading, setDbLoading] = useState(false);

  // 차트에서 날짜 클릭 시 DB에서 해당 날짜 기사를 로드
  useEffect(() => {
    if (selectedDate) {
      setActiveCategory('All');
      setDbLoading(true);
      fetchNewsByDate(selectedDate)
        .then(data => setDbArticles(data))
        .catch(err => {
          console.error('Failed to fetch articles by date:', err);
          setDbArticles([]);
        })
        .finally(() => setDbLoading(false));
    } else {
      setDbArticles([]);
    }
  }, [selectedDate]);

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { All: articles.length };
    CATEGORIES.slice(1).forEach(cat => {
      counts[cat] = articles.filter(a => a.category === cat).length;
    });
    return counts;
  }, [articles]);

  const filteredAndSortedArticles = useMemo(() => {
    let filtered = articles;

    if (activeCategory !== 'All') {
      filtered = articles.filter(a => a.category === activeCategory);
    }
    
    if (activeCrudeType !== 'All') {
      filtered = filtered.filter(a => {
        const impact = a.impact_by_crude?.[activeCrudeType];
        if (impact) {
          return Math.abs(impact.score) > 0;
        }
        return Math.abs(a.impact_score) > 0;
      });
    }

    return [...filtered].sort((a, b) => {
      if (sortOrder === 'impact') {
        const scoreA = activeCrudeType !== 'All' && a.impact_by_crude?.[activeCrudeType] 
          ? a.impact_by_crude[activeCrudeType].score 
          : a.impact_score;
        const scoreB = activeCrudeType !== 'All' && b.impact_by_crude?.[activeCrudeType] 
          ? b.impact_by_crude[activeCrudeType].score 
          : b.impact_score;
        return Math.abs(scoreB) - Math.abs(scoreA);
      }
      return new Date(b.article.published_at).getTime() - new Date(a.article.published_at).getTime();
    });
  }, [articles, activeCategory, activeCrudeType, sortOrder]);

  const handleRetry = useCallback(() => {
    refetch?.();
  }, [refetch]);

  // 데이터소스 뱃지 컬러
  const getSourceColor = (source: string) => {
    switch (source) {
      case 'nyt': return { bg: 'rgba(255, 255, 255, 0.08)', color: '#e4e8ef', label: 'NYT' };
      case 'guardian': return { bg: 'rgba(0, 90, 160, 0.15)', color: '#00A3CC', label: 'Guardian' };
      case 'naver_news': return { bg: 'rgba(0, 200, 80, 0.1)', color: '#00C850', label: 'Naver' };
      default: return { bg: 'rgba(255, 107, 53, 0.1)', color: '#FF6B35', label: source };
    }
  };

  const renderContent = () => {
    // 날짜가 선택된 경우: DB 기사 표시
    if (selectedDate) {
      if (dbLoading) {
        return (
          <div className="news-grid">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} height="160px" />)}
          </div>
        );
      }

      if (dbArticles.length === 0) {
        return (
          <EmptyState
            icon="news"
            title={`${selectedDate}에 수집된 기사가 없습니다`}
            description="다른 날짜를 선택하거나 차트의 ◆ 마커를 클릭해 보세요."
          />
        );
      }

      return (
        <div className="news-grid">
          {dbArticles.map((article, index) => {
            const sc = getSourceColor(article.data_source);
            return (
              <div
                key={article.id}
                className="news-card-container"
                style={{ animationDelay: `${index * 0.03}s` }}
              >
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="db-news-card"
                >
                  <div className="db-news-card-header">
                    <span className="db-news-source-badge" style={{ background: sc.bg, color: sc.color }}>
                      {sc.label}
                    </span>
                    <span className="db-news-date">
                      {new Date(article.published_at).toLocaleDateString('ko-KR', {
                        year: 'numeric', month: 'short', day: 'numeric'
                      })}
                    </span>
                  </div>
                  <h4 className="db-news-title">{article.title}</h4>
                  {article.description && (
                    <p className="db-news-description">{article.description}</p>
                  )}
                  {article.source_name && (
                    <span className="db-news-source-name">{article.source_name}</span>
                  )}
                </a>
              </div>
            );
          })}
        </div>
      );
    }

    // 기본: LLM 분류된 기사 표시
    if (loading) {
      return (
        <div className="news-grid">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} height="180px" />)}
        </div>
      );
    }
    if (error) {
      return (
        <div className="error-fallback-partial">
          <div className="error-fallback-icon">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="10" cy="10" r="8.5" />
              <line x1="7" y1="7" x2="13" y2="13" />
              <line x1="13" y1="7" x2="7" y2="13" />
            </svg>
          </div>
          <p className="error-fallback-title">뉴스 데이터를 불러올 수 없습니다</p>
          <p className="error-fallback-module">{error.message}</p>
          <button className="error-retry-button" onClick={handleRetry}>
            재시도
          </button>
        </div>
      );
    }
    if (filteredAndSortedArticles.length === 0) {
      return (
        <EmptyState
          icon="news"
          title="선택한 카테고리에 해당하는 뉴스가 없습니다"
          description="다른 카테고리를 선택해 보세요."
        />
      );
    }
    return (
      <div className="news-grid">
        {filteredAndSortedArticles.map((article, index) => (
          <div 
            key={article.article.id} 
            className="news-card-container" 
            style={{ animationDelay: `${index * 0.05}s` }}
          >
            <NewsCard article={article} activeCrudeType={activeCrudeType !== 'All' ? activeCrudeType : undefined} />
          </div>
        ))}
      </div>
    );
  };

  const handleCategoryClick = (cat: Category) => {
    setSelectedDate(null);
    setActiveCategory(cat);
  }

  return (
    <Card title="News Explorer" className="news-explorer-card">
      <div className="news-explorer-controls">
        <div className="category-tabs">
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              className={`category-tab ${activeCategory === cat && !selectedDate ? 'active' : ''}`}
              onClick={() => handleCategoryClick(cat)}
              onMouseEnter={() => setHighlightedCategory(cat === 'All' ? null : cat as any)}
              onMouseLeave={() => setHighlightedCategory(null)}
            >
              <Badge category={cat === 'All' ? 'all' : cat as any} />
              <span className="category-count">{categoryCounts[cat] || 0}</span>
            </button>
          ))}
        </div>
        <div className="sort-and-filter">
          {selectedDate && (
            <div className="date-filter-indicator">
              <span className="date-filter-diamond">◆</span>
              <span>{selectedDate} · {dbArticles.length}건의 기사</span>
              <button onClick={() => setSelectedDate(null)}>&times;</button>
            </div>
          )}
          {!selectedDate && (
            <>
              <div className="crude-filter-pills">
                {CRUDE_TYPES.map(crude => (
                  <button
                    key={crude}
                    className={`crude-pill ${activeCrudeType === crude ? 'active' : ''}`}
                    onClick={() => setActiveCrudeType(crude)}
                  >
                    {crude === 'All' ? 'All Crudes' : crude.charAt(0).toUpperCase() + crude.slice(1)}
                  </button>
                ))}
              </div>
              <div className="sort-toggle">
                <button onClick={() => setSortOrder('time')} className={sortOrder === 'time' ? 'active' : ''}>Time</button>
                <button onClick={() => setSortOrder('impact')} className={sortOrder === 'impact' ? 'active' : ''}>Impact</button>
              </div>
            </>
          )}
        </div>
      </div>
      {renderContent()}
    </Card>
  );
};
