import React, { useState } from 'react';
import type { ClassifiedArticle } from '../../types/news';
import { Badge } from '../common/Badge';
import { SimilarEventsPopup } from './SimilarEventsPopup';
import './NewsCard.css';

interface NewsCardProps {
  article: ClassifiedArticle;
}

const ImpactScore: React.FC<{ score: number }> = ({ score }) => {
  const direction = score > 0 ? 'bull' : score < 0 ? 'bear' : 'neutral';
  const size = Math.abs(score);
  const style = {
    fontSize: `${12 + size * 1.5}px`,
    fontWeight: 600,
  };
  return (
    <span className={`impact-score impact-${direction}`} style={style}>
      {score > 0 ? '+' : ''}{score}
    </span>
  );
};

const getTimeAgo = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  let interval = seconds / 31536000;
  if (interval > 1) return `${Math.floor(interval)}년 전`;
  interval = seconds / 2592000;
  if (interval > 1) return `${Math.floor(interval)}달 전`;
  interval = seconds / 86400;
  if (interval > 1) return `${Math.floor(interval)}일 전`;
  interval = seconds / 3600;
  if (interval > 1) return `${Math.floor(interval)}시간 전`;
  interval = seconds / 60;
  if (interval > 1) return `${Math.floor(interval)}분 전`;
  return `${Math.floor(seconds)}초 전`;
};

export const NewsCard: React.FC<NewsCardProps> = ({ article }) => {
  const [showSimilar, setShowSimilar] = useState(false);

  return (
    <>
      <div className="news-card">
        <div className="news-card-header">
          <Badge category={article.category as any} />
          <ImpactScore score={article.impact_score} />
        </div>
        <a href={article.article.url} target="_blank" rel="noopener noreferrer" className="news-card-title">
          {article.article.title}
        </a>
        <div className="news-card-meta">
          <span>{article.article.source}</span>
          <span>·</span>
          <span>{getTimeAgo(article.article.published_at)}</span>
        </div>
        <p className="news-card-summary">{article.impact_summary}</p>
        <div className="news-card-actions">
          <button className="ghost-button" onClick={() => setShowSimilar(true)}>
            유사 사례
          </button>
        </div>
      </div>
      {showSimilar && (
        <SimilarEventsPopup
          query={article.article.title}
          onClose={() => setShowSimilar(false)}
        />
      )}
    </>
  );
};
