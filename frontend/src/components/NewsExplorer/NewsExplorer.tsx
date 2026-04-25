import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { Card } from '../common/Card';
import { useNewsData } from '../../hooks/useNewsData';
import { NewsCard } from './NewsCard';
import { Skeleton } from '../common/Skeleton';
import { Badge } from '../common/Badge';
import { EmptyState } from '../common/EmptyState';
import { useDashboardContext } from '../../context/DashboardContext';
import './NewsExplorer.css';

type SortOrder = 'time' | 'impact';
type Category = 'All' | 'geopolitics' | 'supply' | 'demand' | 'macro' | 'climate' | 'speculation';

const CATEGORIES: Category[] = ['All', 'geopolitics', 'supply', 'demand', 'macro', 'climate', 'speculation'];

export const NewsExplorer: React.FC = () => {
  const { articles, loading, error, refetch } = useNewsData();
  const { selectedDate, setSelectedDate, setHighlightedCategory } = useDashboardContext();
  const [activeCategory, setActiveCategory] = useState<Category>('All');
  const [sortOrder, setSortOrder] = useState<SortOrder>('time');

  // If a date is selected from the chart, reset the category filter
  useEffect(() => {
    if (selectedDate) {
      setActiveCategory('All');
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

    if (selectedDate) {
      filtered = articles.filter(a => a.article.published_at.startsWith(selectedDate));
    } else if (activeCategory !== 'All') {
      filtered = articles.filter(a => a.category === activeCategory);
    }

    return [...filtered].sort((a, b) => {
      if (sortOrder === 'impact') {
        return Math.abs(b.impact_score) - Math.abs(a.impact_score);
      }
      // Default to time
      return new Date(b.article.published_at).getTime() - new Date(a.article.published_at).getTime();
    });
  }, [articles, activeCategory, sortOrder, selectedDate]);

  const handleRetry = useCallback(() => {
    refetch?.();
  }, [refetch]);

  const renderContent = () => {
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
          title={selectedDate
            ? `${selectedDate}에 등록된 중요 뉴스가 없습니다`
            : '선택한 카테고리에 해당하는 뉴스가 없습니다'}
          description="다른 날짜 또는 카테고리를 선택해 보세요."
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
            <NewsCard article={article} />
          </div>
        ))}
      </div>
    );
  };

  const handleCategoryClick = (cat: Category) => {
    setSelectedDate(null); // Clear date filter when a category is clicked
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
              <Badge category={cat === 'All' ? 'default' : cat} />
              <span className="category-count">{categoryCounts[cat] || 0}</span>
            </button>
          ))}
        </div>
        <div className="sort-and-filter">
          {selectedDate && (
            <div className="date-filter-indicator">
              <span>Filtered by: {selectedDate}</span>
              <button onClick={() => setSelectedDate(null)}>&times;</button>
            </div>
          )}
          <div className="sort-toggle">
            <button onClick={() => setSortOrder('time')} className={sortOrder === 'time' ? 'active' : ''}>Time</button>
            <button onClick={() => setSortOrder('impact')} className={sortOrder === 'impact' ? 'active' : ''}>Impact</button>
          </div>
        </div>
      </div>
      {renderContent()}
    </Card>
  );
};
