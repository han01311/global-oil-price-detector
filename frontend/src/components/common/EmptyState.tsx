import React from 'react';
import './EmptyState.css';

type IconType = 'box' | 'news' | 'chart' | 'briefing';

interface EmptyStateProps {
  icon?: IconType;
  title: string;
  description?: string;
}

const icons: Record<IconType, React.ReactNode> = {
  box: (
    <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M24 4L42 14V34L24 44L6 34V14L24 4Z" />
      <path d="M6 14L24 24" />
      <path d="M24 24V44" />
      <path d="M24 24L42 14" />
    </svg>
  ),
  news: (
    <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="6" y="8" width="36" height="32" rx="2" />
      <line x1="14" y1="16" x2="34" y2="16" />
      <line x1="14" y1="22" x2="34" y2="22" />
      <line x1="14" y1="28" x2="26" y2="28" />
    </svg>
  ),
  chart: (
    <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6,38 16,28 24,32 34,18 42,22" />
      <line x1="6" y1="42" x2="42" y2="42" />
      <line x1="6" y1="10" x2="6" y2="42" />
    </svg>
  ),
  briefing: (
    <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="10" y="6" width="28" height="36" rx="2" />
      <line x1="16" y1="14" x2="32" y2="14" />
      <line x1="16" y1="20" x2="32" y2="20" />
      <line x1="16" y1="26" x2="28" y2="26" />
      <circle cx="24" cy="34" r="3" />
    </svg>
  ),
};

export const EmptyState: React.FC<EmptyStateProps> = ({ icon = 'box', title, description }) => {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">{icons[icon]}</div>
      <p className="empty-state-title">{title}</p>
      {description && <p className="empty-state-description">{description}</p>}
    </div>
  );
};
