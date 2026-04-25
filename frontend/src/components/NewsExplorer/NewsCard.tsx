import React, { useState } from 'react';
import type { ClassifiedArticle } from '../../types/news';
import { Badge } from '../common/Badge';
import { SimilarEventsPopup } from './SimilarEventsPopup';
import './NewsCard.css';

interface NewsCardProps {
  article: ClassifiedArticle;
  activeCrudeType?: string;
}

const CrudeImpacts: React.FC<{ 
  impacts?: ClassifiedArticle['impact_by_crude'], 
  globalScore?: number,
  globalSummary?: string
}> = ({ impacts, globalScore, globalSummary }) => {
  if (!impacts || Object.keys(impacts).length === 0) {
    if (globalScore !== undefined) {
      const direction = globalScore > 0 ? 'bull' : globalScore < 0 ? 'bear' : 'neutral';
      return (
        <div className="crude-impacts-container">
          <div className={`crude-impact-badge impact-${direction}`} title={globalSummary}>
            <span className="crude-label">Impact</span>
            <span className="crude-score">{globalScore > 0 ? '+' : ''}{globalScore}</span>
          </div>
        </div>
      );
    }
    return null;
  }
  
  return (
    <div className="crude-impacts-container">
      {Object.entries(impacts).map(([crudeType, impact]) => {
        const direction = impact.direction === 'bullish' ? 'bull' : impact.direction === 'bearish' ? 'bear' : 'neutral';
        const label = crudeType.charAt(0).toUpperCase() + crudeType.slice(1);
        return (
          <div key={crudeType} className={`crude-impact-badge impact-${direction}`} title={impact.rationale}>
            <span className="crude-label">{label}</span>
            <span className="crude-score">{impact.score > 0 ? '+' : ''}{impact.score}</span>
          </div>
        );
      })}
    </div>
  );
};

const RelatedCrudeTags: React.FC<{ impacts?: ClassifiedArticle['impact_by_crude'] }> = ({ impacts }) => {
  if (!impacts) return null;
  const relatedCrudes = Object.entries(impacts)
    .filter(([_, impact]) => Math.abs(impact.score) > 0)
    .map(([crudeType]) => crudeType.charAt(0).toUpperCase() + crudeType.slice(1));
  
  if (relatedCrudes.length === 0) return null;

  return (
    <div className="related-crude-tags">
      {relatedCrudes.map(crude => (
        <span key={crude} className="crude-tag">#{crude}</span>
      ))}
    </div>
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

export const NewsCard: React.FC<NewsCardProps> = ({ article, activeCrudeType }) => {
  const [showSimilar, setShowSimilar] = useState(false);

  return (
    <>
      <div className="news-card">
        <div className="news-card-header">
          <Badge category={article.category as any} />
          <CrudeImpacts 
            impacts={article.impact_by_crude} 
            globalScore={article.impact_score}
            globalSummary={article.impact_summary}
          />
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
          <RelatedCrudeTags impacts={article.impact_by_crude} />
        </div>
      </div>
      {showSimilar && (
        <SimilarEventsPopup
          query={article.article.title}
          crudeType={activeCrudeType}
          onClose={() => setShowSimilar(false)}
        />
      )}
    </>
  );
};
