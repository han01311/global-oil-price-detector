import React, { useState, useMemo, useEffect } from 'react';
import { Card } from '../common/Card';
import { useNewsData } from '../../hooks/useNewsData';
import { NewsCard } from './NewsCard';
import { Skeleton } from '../common/Skeleton';
import { Badge } from '../common/Badge';
import { useDashboardContext } from '../../context/DashboardContext';
import './NewsExplorer.css';

type SortOrder = 'time' | 'impact';
type Category = 'All' | 'geopolitics' | 'supply' | 'demand' | 'macro' | 'climate' | 'speculation';

const CATEGORIES: Category[] = ['All', 'geopolitics', 'supply', 'demand', 'macro', 'climate', 'speculation'];

export const NewsExplorer: React.FC = () => {
  const { articles, loading, error } = useNewsData();
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

  const renderContent = () => {
    if (loading) {
      return (
        <div className="news-grid">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} height="180px" />)}
        </div>
      );
    }
    if (error) {
      return <p style={{ color: 'var(--color-error)' }}>Error loading news: {error.message}</p>;
    }
    if (filteredAndSortedArticles.length === 0) {
      return <p>{selectedDate ? `No news found for ${selectedDate}.` : 'No relevant news found for this category.'}</p>;
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
