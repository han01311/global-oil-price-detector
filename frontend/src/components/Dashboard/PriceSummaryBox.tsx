import React from 'react';
import type { OilPrice } from '../../types/price';
import type { ForecastResult } from '../../types/forecast';
import './PriceSummaryBox.css';

interface PriceSummaryBoxProps {
  latestPrice: (OilPrice & { change?: number }) | null;
  forecast: ForecastResult | null;
  loading: boolean;
}

export const PriceSummaryBox: React.FC<PriceSummaryBoxProps> = ({ latestPrice, forecast, loading }) => {
  if (loading || !latestPrice || !forecast) {
    return null;
  }

  const crudes = [
    { id: 'dubai', label: 'Dubai', price: latestPrice.dubai, forecast: forecast.forecasts_by_crude?.dubai },
    { id: 'wti', label: 'WTI', price: latestPrice.wti, forecast: forecast.forecasts_by_crude?.wti },
    { id: 'brent', label: 'Brent', price: latestPrice.brent, forecast: forecast.forecasts_by_crude?.brent }
  ];

  return (
    <div className="price-summary-container">
      {crudes.map(crude => {
        if (crude.price === undefined || crude.price === null || !crude.forecast) return null;
        
        const predictedPrice = crude.forecast.estimated_7d;
        const changeVal = predictedPrice - crude.price;
        const changePct = (changeVal / crude.price) * 100;
        const isUp = changeVal >= 0;

        return (
          <div key={crude.id} className="price-summary-card">
            <div className="summary-header">
              <span className="summary-title">{crude.label}</span>
            </div>
            <div className="summary-body">
              <div className="summary-current">
                <span className="summary-label">현재가</span>
                <span className="summary-value">${crude.price.toFixed(2)}</span>
              </div>
              <div className="summary-arrow">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                  <polyline points="12 5 19 12 12 19"></polyline>
                </svg>
              </div>
              <div className="summary-forecast">
                <span className="summary-label">7일 전망치</span>
                <span className={`summary-value ${isUp ? 'bull' : 'bear'}`}>
                  ${predictedPrice.toFixed(2)}
                </span>
                <span className={`summary-pct ${isUp ? 'bull' : 'bear'}`}>
                  {isUp ? '+' : ''}{changeVal.toFixed(2)} ({changePct.toFixed(2)}%)
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
