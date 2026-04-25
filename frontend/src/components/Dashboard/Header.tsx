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
        {loading ? (
          <>
            <Skeleton width="200px" height="2rem" />
            <Skeleton width="200px" height="2rem" />
          </>
        ) : (
          <>
            {dubaiPrice !== null && dubaiPrice !== undefined && (
              <div className="header-price-item">
                <Tooltip content="Dubai Crude. 중동 지역에서 생산되는 원유 벤치마크 가격.">
                  <span className="price-label">Dubai</span>
                </Tooltip>
                <PriceDisplay value={dubaiPrice} size="medium" />
              </div>
            )}
            {wtiPrice !== null && wtiPrice !== undefined && (
              <div className="header-price-item">
                <Tooltip content="West Texas Intermediate. 미국 텍사스에서 생산되는 경질 원유 벤치마크 가격.">
                  <span className="price-label">WTI</span>
                </Tooltip>
                <PriceDisplay value={wtiPrice} change={priceChange} size="medium" />
              </div>
            )}
            {brentPrice !== null && brentPrice !== undefined && (
              <div className="header-price-item">
                <Tooltip content="Brent Crude. 북해에서 생산되는 원유로 글로벌 유가의 국제 기준 벤치마크.">
                  <span className="price-label">Brent</span>
                </Tooltip>
                <PriceDisplay value={brentPrice} size="medium" />
              </div>
            )}
          </>
        )}
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
