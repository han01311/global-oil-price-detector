import React from 'react';
import { Link } from 'react-router-dom';
import { PriceDisplay } from '../common/PriceDisplay';
import { Skeleton } from '../common/Skeleton';
import { Tooltip } from '../common/Tooltip';
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

export const Header: React.FC<HeaderProps> = ({ latestPrice, forecast, loading, isBlackSwan }) => {
  const dubaiPrice = latestPrice?.dubai;
  const wtiPrice = latestPrice?.wti;
  const brentPrice = latestPrice?.brent;
  const priceChange = latestPrice?.change;
  const lastUpdated = forecast?.generated_at ? new Date(forecast.generated_at).toLocaleString() : 'N/A';

  return (
    <header className="dashboard-header-main">
      <div className="header-logo">
        Petro-AX
      </div>
      <div className="header-prices">
        {/* Prices moved to PriceSummaryBox above the chart */}
      </div>
      <div className="header-meta">
        {isBlackSwan && <BlackSwanBadge />}
        {loading ? (
          <Skeleton width="220px" height="1rem" />
        ) : (
          <span className="last-updated">Last updated: {lastUpdated}</span>
        )}
        <Link to="/admin" className="header-admin-link" title="Data Pipeline Admin">
          ⚙
        </Link>
      </div>
    </header>
  );
};
