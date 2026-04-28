import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { Card } from '../common/Card';
import { useNewsData } from '../../hooks/useNewsData';
import { NewsCard } from './NewsCard';
import { Skeleton } from '../common/Skeleton';
import { Badge } from '../common/Badge';
import { EmptyState } from '../common/EmptyState';
import { useDashboardContext } from '../../context/DashboardContext';
import { fetchNewsByDate } from '../../services/api';
import type { ClassifiedArticle } from '../../types/news';
import './NewsExplorer.css';

type SortOrder = 'time' | 'impact';
type Category = 'All' | 'geopolitics' | 'supply' | 'demand' | 'macro' | 'climate' | 'speculation' | 'other';
type CrudeType = 'All' | 'dubai' | 'brent' | 'wti';

const KNOWN_CATEGORIES = ['geopolitics', 'supply', 'demand', 'macro', 'climate', 'speculation'];
const CATEGORIES: Category[] = ['All', 'geopolitics', 'supply', 'demand', 'macro', 'climate', 'speculation', 'other'];
const CRUDE_TYPES: CrudeType[] = ['All', 'dubai', 'brent', 'wti'];

export const NewsExplorer: React.FC = () => {
  const { articles, loading, error, refetch } = useNewsData();
  const { selectedDate, setSelectedDate, setHighlightedCategory } = useDashboardContext();
  const [activeCategory, setActiveCategory] = useState<Category>('All');
  const [activeCrudeType, setActiveCrudeType] = useState<CrudeType>('All');
  const [sortOrder, setSortOrder] = useState<SortOrder>('time');

  // DB 기사 (차트 날짜 클릭 시 로드)
  const [dbArticles, setDbArticles] = useState<ClassifiedArticle[]>([]);
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

  const targetArticles = selectedDate ? dbArticles : articles;

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { All: targetArticles.length, other: 0 };
    KNOWN_CATEGORIES.forEach(cat => {
      counts[cat] = targetArticles.filter(a => a.category === cat).length;
    });
    counts['other'] = targetArticles.filter(a => !KNOWN_CATEGORIES.includes(a.category)).length;
    return counts;
  }, [targetArticles]);

  const filteredAndSortedArticles = useMemo(() => {
    let filtered = targetArticles;

    if (activeCategory !== 'All') {
      if (activeCategory === 'other') {
        filtered = targetArticles.filter(a => !KNOWN_CATEGORIES.includes(a.category));
      } else {
        filtered = targetArticles.filter(a => a.category === activeCategory);
      }
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
  }, [targetArticles, activeCategory, activeCrudeType, sortOrder]);

  const handleRetry = useCallback(() => {
    refetch?.();
  }, [refetch]);

  const renderContent = () => {
    if (selectedDate && dbLoading) {
      return (
        <div className="news-grid">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} height="160px" />)}
        </div>
      );
    }

    if (!selectedDate && loading) {
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
      const emptyTitle = selectedDate 
        ? `${selectedDate}에 수집된 기사가 없습니다`
        : "선택한 카테고리에 해당하는 뉴스가 없습니다";
      const emptyDesc = selectedDate
        ? "다른 날짜를 선택하거나 다른 카테고리로 필터링해 보세요."
        : "다른 카테고리를 선택해 보세요.";
      
      return (
        <EmptyState
          icon="news"
          title={emptyTitle}
          description={emptyDesc}
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
    setActiveCategory(cat);
  }

  return (
    <Card title="News Explorer" className="news-explorer-card">
      <div className="news-explorer-controls">
        <div className="category-tabs">
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              className={`category-tab ${activeCategory === cat ? 'active' : ''}`}
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
          <div className="date-filter-container" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {selectedDate && (
              <div className="date-badge">
                🗓 {selectedDate} 
                <span style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginLeft: '4px' }}>({dbArticles.length}건)</span>
              </div>
            )}
            <button 
              className={`today-button ${selectedDate === null ? 'active' : ''}`}
              onClick={() => setSelectedDate(null)}
            >
              {selectedDate ? '최신 뉴스로 돌아가기' : '최신 뉴스'}
            </button>
          </div>
        </div>
      </div>
      {renderContent()}
    </Card>
  );
};
