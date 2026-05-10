import React, { useState, useEffect } from 'react';
import type { OilPrice } from '../../types/price';
import type { ForecastResult } from '../../types/forecast';
import { fetchExchangeRate, type ExchangeRateData } from '../../services/api';
import './PriceSummaryBox.css';

interface PriceSummaryBoxProps {
  latestPrice: (OilPrice & { change?: number }) | null;
  forecast: ForecastResult | null;
  loading: boolean;
}

export const PriceSummaryBox: React.FC<PriceSummaryBoxProps> = ({ latestPrice, forecast, loading }) => {
  const [currency, setCurrency] = useState<'USD' | 'KRW'>('USD');
  const [exchangeRate, setExchangeRate] = useState<ExchangeRateData | null>(null);
  const [rateLoading, setRateLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const loadRate = async () => {
      setRateLoading(true);
      try {
        const data = await fetchExchangeRate();
        if (!cancelled && data?.krw_usd) {
          setExchangeRate(data);
        }
      } catch (err) {
        console.error('[PriceSummaryBox] Exchange rate fetch error:', err);
      } finally {
        if (!cancelled) setRateLoading(false);
      }
    };
    loadRate();
    return () => { cancelled = true; };
  }, []);

  if (loading || !latestPrice || !forecast) {
    return null;
  }

  const rate = exchangeRate?.krw_usd ?? 0;
  const isKRW = currency === 'KRW' && rate > 0;

  const formatPrice = (usdPrice: number) => {
    if (isKRW) {
      const krwPrice = usdPrice * rate;
      return `₩${krwPrice.toLocaleString('ko-KR', { maximumFractionDigits: 0 })}`;
    }
    return `$${usdPrice.toFixed(2)}`;
  };

  const formatChange = (changeVal: number) => {
    if (isKRW) {
      const krwChange = changeVal * rate;
      return `${krwChange >= 0 ? '+' : ''}${krwChange.toLocaleString('ko-KR', { maximumFractionDigits: 0 })}`;
    }
    return `${changeVal >= 0 ? '+' : ''}${changeVal.toFixed(2)}`;
  };

  const crudes = [
    { id: 'dubai', label: 'Dubai', price: latestPrice.dubai, forecast: forecast.forecasts_by_crude?.dubai },
    { id: 'wti', label: 'WTI', price: latestPrice.wti, forecast: forecast.forecasts_by_crude?.wti },
    { id: 'brent', label: 'Brent', price: latestPrice.brent, forecast: forecast.forecasts_by_crude?.brent }
  ];

  return (
    <div className="price-summary-container">
      {/* USD / KRW 토글 */}
      {rate > 0 && (
        <div className="currency-toggle-wrapper">
          <div className="currency-toggle">
            <button
              className={`toggle-btn ${currency === 'USD' ? 'active' : ''}`}
              onClick={() => setCurrency('USD')}
            >
              USD ($)
            </button>
            <button
              className={`toggle-btn ${currency === 'KRW' ? 'active' : ''}`}
              onClick={() => setCurrency('KRW')}
            >
              KRW (₩)
            </button>
          </div>
          {isKRW && exchangeRate && (
            <span className="exchange-rate-badge" title={`기준일: ${exchangeRate.date}`}>
              1 USD = ₩{rate.toLocaleString('ko-KR')}
              <span className="rate-source">한국수출입은행</span>
            </span>
          )}
        </div>
      )}

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
                <span className="summary-value">{formatPrice(crude.price)}</span>
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
                  {formatPrice(predictedPrice)}
                </span>
                <span className={`summary-pct ${isUp ? 'bull' : 'bear'}`}>
                  {formatChange(changeVal)} ({changePct.toFixed(2)}%)
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
