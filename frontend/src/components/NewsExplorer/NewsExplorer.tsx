import React, { useState, useMemo } from 'react';
import { Card } from '../common/Card';
import { useNewsData } from '../../hooks/useNewsData';
import { NewsCard } from './NewsCard';
import { Skeleton } from '../common/Skeleton';
import { Badge } from '../common/Badge';
import './NewsExplorer.css';

type SortOrder = 'time' | 'impact';
type Category = 'All' | 'geopolitics' | 'supply' | 'demand' | 'macro' | 'climate' | 'speculation';

const CATEGORIES: Category[] = ['All', 'geopolitics', 'supply', 'demand', 'macro', 'climate', 'speculation'];

export const NewsExplorer: React.FC = () => {
  const { articles, loading, error } = useNewsData();
  const [activeCategory, setActiveCategory] = useState<Category>('All');
  const [sortOrder, setSortOrder] = useState<SortOrder>('time');

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

    return [...filtered].sort((a, b) => {
      if (sortOrder === 'impact') {
        return Math.abs(b.impact_score) - Math.abs(a.impact_score);
      }
      // Default to time
      return new Date(b.article.published_at).getTime() - new Date(a.article.published_at).getTime();
    });
  }, [articles, activeCategory, sortOrder]);

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
      return <p>No relevant news found for this category.</p>;
    }
    return (
      <div className="news-grid">
        {filteredAndSortedArticles.map(article => (
          <NewsCard key={article.article.id} article={article} />
        ))}
      </div>
    );
  };

  return (
    <Card title="News Explorer" className="news-explorer-card">
      <div className="news-explorer-controls">
        <div className="category-tabs">
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              className={`category-tab ${activeCategory === cat ? 'active' : ''}`}
              onClick={() => setActiveCategory(cat)}
            >
              <Badge category={cat === 'All' ? 'default' : cat} />
              <span className="category-count">{categoryCounts[cat] || 0}</span>
            </button>
          ))}
        </div>
        <div className="sort-toggle">
          <button onClick={() => setSortOrder('time')} className={sortOrder === 'time' ? 'active' : ''}>Time</button>
          <button onClick={() => setSortOrder('impact')} className={sortOrder === 'impact' ? 'active' : ''}>Impact</button>
        </div>
      </div>
      {renderContent()}
    </Card>
  );
};
