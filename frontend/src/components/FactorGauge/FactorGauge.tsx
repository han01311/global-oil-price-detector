import React from 'react';
import { Card } from '../common/Card';
import { useFactorSummary } from '../../hooks/useFactorSummary';
import { Skeleton } from '../common/Skeleton';
import { Badge } from '../common/Badge';
import { FactorScore } from '../../types/news';
import './FactorGauge.css';

const getSentimentLabel = (score: number): string => {
  if (score > 2.5) return '강한 상승';
  if (score > 0.5) return '약한 상승';
  if (score < -2.5) return '강한 하락';
  if (score < -0.5) return '약한 하락';
  return '중립';
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

const FactorBar: React.FC<{ factor: FactorScore }> = ({ factor }) => {
  const score = factor.avg_score;
  const direction = score >= 0 ? 'bull' : 'bear';
  const width = `${(Math.abs(score) / 5) * 50}%`; // Max 50% width from center
  const style = { width };

  return (
    <li className="factor-item">
      <span className="factor-label">
        <Badge category={factor.category as any} />
      </span>
      <div className="factor-bar-track">
        <div className={`factor-bar ${direction}`} style={style}></div>
      </div>
      <span className={`factor-score ${direction}`}>
        {score >= 0 ? '+' : ''}{score.toFixed(1)}
      </span>
      <span className="factor-count">({factor.article_count}건)</span>
    </li>
  );
};

export const FactorGauge: React.FC = () => {
  const { summary, loading, error } = useFactorSummary();

  const renderContent = () => {
    if (loading) {
      return (
        <div className="factor-list">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} height="24px" />)}
        </div>
      );
    }
    if (error) {
      return <p style={{ color: 'var(--color-error)' }}>Error: {error.message}</p>;
    }
    if (!summary || summary.factors.length === 0) {
      return <p>No factor data available.</p>;
    }

    const totalArticles = summary.factors.reduce((acc, f) => acc + f.article_count, 0);
    const sentimentScore = summary.overall_sentiment;
    const sentimentDirection = sentimentScore > 0 ? 'bull' : sentimentScore < 0 ? 'bear' : 'neutral';

    return (
      <div className="factor-gauge-container">
        <ul className="factor-list">
          {summary.factors.map(factor => <FactorBar key={factor.category} factor={factor} />)}
        </ul>
        <div className="factor-gauge-footer">
          <div className="overall-sentiment">
            <span className="overall-sentiment-label">종합 센티먼트</span>
            <span className={`overall-sentiment-value ${sentimentDirection}`}>
              {sentimentScore > 0 ? '+' : ''}{sentimentScore.toFixed(2)}
              <span style={{ fontSize: '12px', marginLeft: '4px' }}>({getSentimentLabel(sentimentScore)})</span>
            </span>
          </div>
          <div className="factor-gauge-meta">
            <span>분석 기사: {totalArticles}건</span>
            <span>갱신: {getTimeAgo(summary.updated_at)}</span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <Card title="Market Factors">
      {renderContent()}
    </Card>
  );
};
