import React, { useState, useEffect } from 'react';
import type { SimilarEvent } from '../../types/news';
import { fetchSimilarEvents } from '../../services/api';
import { Skeleton } from '../common/Skeleton';
import { Badge } from '../common/Badge';
import './SimilarEventsPopup.css';

interface SimilarEventsPopupProps {
  query: string;
  onClose: () => void;
}

const formatChange = (change: number | null | undefined): React.ReactNode => {
  if (change === null || change === undefined) {
    return <span className="change-neutral">N/A</span>;
  }
  const direction = change > 0 ? 'bull' : 'bear';
  return (
    <span className={`change-${direction}`}>
      {change > 0 ? '+' : ''}{change.toFixed(2)}%
    </span>
  );
};

export const SimilarEventsPopup: React.FC<SimilarEventsPopupProps> = ({ query, onClose }) => {
  const [events, setEvents] = useState<SimilarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const loadSimilarEvents = async () => {
      try {
        setLoading(true);
        const data = await fetchSimilarEvents(query);
        setEvents(data);
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Failed to fetch similar events'));
      } finally {
        setLoading(false);
      }
    };
    loadSimilarEvents();
  }, [query]);

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
            <div className="event-impact">
              <span>7D WTI Change: {formatChange(event.wti_change_7d)}</span>
              <span className="event-similarity">Similarity: {(event.similarity * 100).toFixed(0)}%</span>
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
