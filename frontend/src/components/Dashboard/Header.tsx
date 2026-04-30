import React from 'react';
import { Link } from 'react-router-dom';
import { Skeleton } from '../common/Skeleton';
import './Header.css';
import type { OilPrice } from '../../types/price';
import type { ForecastResult } from '../../types/forecast';

interface HeaderProps {
  latestPrice: (OilPrice & { change?: number }) | null;
  forecast: ForecastResult | null;
  loading: boolean;
  isBlackSwan?: boolean;
}

const BlackSwanBadge: React.FC = () => (
  <span className="black-swan-badge">
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 1.5L1 14h14L8 1.5z" />
      <line x1="8" y1="6" x2="8" y2="10" />
      <line x1="8" y1="12" x2="8" y2="12.5" />
    </svg>
    Extreme Volatility Warning
  </span>
);

export const Header: React.FC<HeaderProps> = ({ forecast, loading, isBlackSwan }) => {
  // 유가 데이터 기준일 (4/29 등 실제 데이터 날짜)
  const dataAsOf = forecast?.data_as_of
    ? new Date(forecast.data_as_of + 'T00:00:00').toLocaleDateString('ko-KR', {
        month: 'short', day: 'numeric',
      })
    : null;

  // 산출 시각 (API 생성 시각)
  const generatedTime = forecast?.generated_at
    ? new Date(forecast.generated_at).toLocaleString('ko-KR', {
        hour: '2-digit', minute: '2-digit',
      })
    : null;

  return (
    <header className="dashboard-header-main">
      <div className="header-logo">
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <defs>
            <linearGradient id="dropGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#4F8EF7"/>
              <stop offset="100%" stopColor="#34C77B"/>
            </linearGradient>
          </defs>
          {/* Droplet outline */}
          <path d="M14 2 C14 2 5 12 5 17.5 C5 22.2 9.03 26 14 26 C18.97 26 23 22.2 23 17.5 C23 12 14 2 14 2Z"
            stroke="url(#dropGrad)" strokeWidth="1.6" fill="none" strokeLinejoin="round"/>
          {/* Lens aperture inside */}
          <circle cx="14" cy="17" r="4.5" stroke="url(#dropGrad)" strokeWidth="1.2" fill="none"/>
          <line x1="14" y1="12.5" x2="14" y2="14.5" stroke="url(#dropGrad)" strokeWidth="1.1" strokeLinecap="round"/>
          <line x1="14" y1="19.5" x2="14" y2="21.5" stroke="url(#dropGrad)" strokeWidth="1.1" strokeLinecap="round"/>
          <line x1="9.5" y1="17" x2="11.5" y2="17" stroke="url(#dropGrad)" strokeWidth="1.1" strokeLinecap="round"/>
          <line x1="16.5" y1="17" x2="18.5" y2="17" stroke="url(#dropGrad)" strokeWidth="1.1" strokeLinecap="round"/>
        </svg>
        <div className="header-logo-text">
          <span className="header-logo-name">
            <span className="header-logo-oil">Oil</span><span className="header-logo-lens">Lens</span>
          </span>
          <span className="header-logo-tagline">Crude Oil Intelligence</span>
        </div>
      </div>
      <div className="header-prices">
        {/* Prices moved to PriceSummaryBox above the chart */}
      </div>
      <div className="header-meta">
        {isBlackSwan && <BlackSwanBadge />}
        {loading ? (
          <Skeleton width="140px" height="1rem" />
        ) : (dataAsOf || generatedTime) ? (
          <span className="last-updated">
            <span className="last-updated-dot" />
            {dataAsOf && <span className="last-updated-date">{dataAsOf} 기준</span>}
            {generatedTime && <span className="last-updated-time">· {generatedTime} 산출</span>}
          </span>
        ) : null}
        <Link to="/admin" className="header-admin-link" title="Data Pipeline Admin">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        </Link>
      </div>
    </header>
  );
};
