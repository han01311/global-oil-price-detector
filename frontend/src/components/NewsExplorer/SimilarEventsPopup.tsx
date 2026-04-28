import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import type { SimilarEvent } from '../../types/news';
import { fetchSimilarEvents } from '../../services/api';
import { Skeleton } from '../common/Skeleton';
import { Badge } from '../common/Badge';
import './SimilarEventsPopup.css';

interface SimilarEventsPopupProps {
  query: string;
  crudeType?: string;
  anchorEl: HTMLElement | null;
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

export const SimilarEventsPopup: React.FC<SimilarEventsPopupProps> = ({ query, crudeType, anchorEl, onClose }) => {
  const [events, setEvents] = useState<SimilarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [popupStyle, setPopupStyle] = useState<React.CSSProperties>({ opacity: 0 }); // Hide initially until positioned
  const popupRef = React.useRef<HTMLDivElement>(null);

  React.useLayoutEffect(() => {
    if (anchorEl && popupRef.current) {
      const rect = anchorEl.getBoundingClientRect();
      const popupRect = popupRef.current.getBoundingClientRect();
      const popupWidth = 420; // Fixed width
      const windowWidth = window.innerWidth;
      const windowHeight = window.innerHeight;
      
      let leftPosition = rect.right + 16;
      // If it overflows on the right, show it on the left
      if (leftPosition + popupWidth > windowWidth) {
        leftPosition = rect.left - popupWidth - 16;
      }
      
      let topPosition = rect.top;
      // If the popup would overflow the bottom of the screen, shift it up
      if (topPosition + popupRect.height > windowHeight - 16) {
        topPosition = windowHeight - popupRect.height - 16;
      }
      // But never let it overflow the top of the screen
      if (topPosition < 16) {
        topPosition = 16;
      }
      
      setPopupStyle({
        position: 'fixed',
        top: topPosition,
        left: leftPosition,
        width: popupWidth,
        maxHeight: 'calc(100vh - 32px)',
        zIndex: 1000,
        opacity: 1, // Show once positioned
        transition: 'top 0.2s ease-out', // Smooth adjustment if content changes
      });
    }
  }, [anchorEl, events, loading]);

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
      return Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} height="80px" style={{ marginBottom: '12px' }} />);
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
            <a href={event.url} target="_blank" rel="noopener noreferrer" className="event-title-container" style={{ textDecoration: 'none', display: 'block', marginBottom: '8px' }}>
              <strong className="event-title" style={{ fontSize: '14px', display: 'block', marginBottom: '4px' }}>
                {event.translated_title || event.title}
              </strong>
              {event.translated_title && event.translated_title !== event.title && (
                <span className="event-original-title" style={{ fontSize: '12px', color: 'var(--color-text-muted)', display: 'block' }}>
                  {event.title}
                </span>
              )}
            </a>
            {event.summary && (
              <p className="event-summary" style={{ fontSize: '12px', color: 'var(--color-text-body)', marginBottom: '8px', lineHeight: 1.4 }}>
                {event.summary}
              </p>
            )}
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

  // If no anchor is provided, default to full screen overlay
  if (!anchorEl) return null;

  return ReactDOM.createPortal(
    <>
      <div className="popup-backdrop" onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 999 }} />
      <div className="popup-content" ref={popupRef} style={popupStyle} onClick={(e) => e.stopPropagation()}>
        <div className="popup-header">
          <h4>유사 과거 사례</h4>
          <button onClick={onClose} className="close-button">&times;</button>
        </div>
        <div className="popup-body">
          {renderContent()}
        </div>
      </div>
    </>,
    document.body
  );
};
