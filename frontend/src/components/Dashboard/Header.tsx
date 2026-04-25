import React from 'react';
import { PriceDisplay } from '../common/PriceDisplay';
import { Skeleton } from '../common/Skeleton';
import './Header.css';
import type { OilPrice } from '../../types/price';
import type { ForecastResult } from '../../types/forecast';

interface HeaderProps {
  latestPrice: (OilPrice & { change?: number }) | null;
  forecast: ForecastResult | null;
  loading: boolean;
}

export const Header: React.FC<HeaderProps> = ({ latestPrice, forecast, loading }) => {
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
            {wtiPrice !== null && wtiPrice !== undefined && (
              <div className="header-price-item">
                <span className="price-label">WTI</span>
                <PriceDisplay value={wtiPrice} change={priceChange} size="medium" />
              </div>
            )}
            {brentPrice !== null && brentPrice !== undefined && (
              <div className="header-price-item">
                <span className="price-label">Brent</span>
                <PriceDisplay value={brentPrice} size="medium" />
              </div>
            )}
          </>
        )}
      </div>
      <div className="header-meta">
        {loading ? (
          <Skeleton width="220px" height="1rem" />
        ) : (
          <span className="last-updated">Last updated: {lastUpdated}</span>
        )}
        {/* Settings Icon Placeholder */}
        <div className="settings-icon"></div>
      </div>
    </header>
  );
};
