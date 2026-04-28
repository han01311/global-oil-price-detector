import React, { useState, useEffect } from 'react';
import type { SimilarEvent } from '../../types/news';
import { fetchSimilarEvents } from '../../services/api';
import { Skeleton } from '../common/Skeleton';
import { Badge } from '../common/Badge';
import './SimilarEventsPopup.css';

interface SimilarEventsPopupProps {
  query: string;
  crudeType?: string;
  onClose: () => void;
}

const formatChange = (change: number | null | undefined): React.ReactNode => {
  if (change === null || change === undefined) {
    return (
      <span 
        className="change-neutral" 
        style={{ fontSize: '10px', border: '1px solid var(--color-border)', padding: '1px 4px', borderRadius: '2px', cursor: 'help' }}
        title="발행일로부터 7일이 경과하지 않아 아직 변동률 데이터를 집계할 수 없습니다."
      >
        집계 대기
      </span>
    );
  }
  const direction = change > 0 ? 'bull' : (change < 0 ? 'bear' : 'neutral');
  return (
    <span className={`change-${direction}`}>
      {change > 0 ? '+' : ''}{change.toFixed(2)}%
    </span>
  );
};

export const SimilarEventsPopup: React.FC<SimilarEventsPopupProps> = ({ query, crudeType, onClose }) => {
  const [events, setEvents] = useState<SimilarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const loadSimilarEvents = async () => {
      try {
        setLoading(true);
        const data = await fetchSimilarEvents(query, crudeType);
        setEvents(data);
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Failed to fetch similar events'));
      } finally {
        setLoading(false);
      }
    };
    loadSimilarEvents();
  }, [query, crudeType]);

  const renderContent = () => {
    if (loading) {
      return Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} height="60px" style={{ marginBottom: '12px' }} />);
    }
    if (error) {
      return <p className="popup-error">Error: {error.message}</p>;
    }
    if (events.length === 0) {
      return <p>No similar past events found.</p>;
    }
    return (
      <ul className="similar-events-list">
        {events.map((event, index) => (
          <li key={index} className="similar-event-item">
            <div className="event-header">
              <Badge category={event.category as any} />
              <span className="event-date">{new Date(event.date).toLocaleDateString()}</span>
            </div>
            <a href={event.url} target="_blank" rel="noopener noreferrer" className="event-title">
              {event.title}
            </a>
            <div className="event-impacts">
              <div style={{ width: '100%', fontSize: '10px', color: 'var(--color-text-muted)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ fontSize: '12px' }}>📉</span>
                <span>이 기사 발행 후 <strong>7일간</strong>의 유가 변동률</span>
                <span className="event-similarity" style={{ marginLeft: 'auto', color: 'var(--color-text-secondary)' }}>
                  유사도: {(event.similarity * 100).toFixed(0)}%
                </span>
              </div>
              <div className="event-impact-item">
                <span>Dubai:</span> {formatChange(event.dubai_change_7d)}
              </div>
              <div className="event-impact-item">
                <span>WTI:</span> {formatChange(event.wti_change_7d)}
              </div>
              <div className="event-impact-item">
                <span>Brent:</span> {formatChange(event.brent_change_7d)}
              </div>
            </div>
          </li>
        ))}
      </ul>
    );
  };

  return (
    <div className="popup-overlay" onClick={onClose}>
      <div className="popup-content" onClick={(e) => e.stopPropagation()}>
        <div className="popup-header">
          <h4>Similar Past Events</h4>
          <button onClick={onClose} className="close-button">&times;</button>
        </div>
        <div className="popup-body">
          {renderContent()}
        </div>
      </div>
    </div>
  );
};
