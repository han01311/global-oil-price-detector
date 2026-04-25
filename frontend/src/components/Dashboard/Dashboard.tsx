import React from 'react';
import { Header } from './Header';
import { PriceChart } from '../PriceChart/PriceChart';
import { FactorGauge } from '../FactorGauge/FactorGauge';
import { AIBriefing } from '../Briefing/AIBriefing';
import { NewsExplorer } from '../NewsExplorer/NewsExplorer';
import { useDashboardData } from '../../hooks/useDashboardData';
import { ErrorBoundary } from '../common/ErrorBoundary';
import './Dashboard.css';

export const Dashboard: React.FC = () => {
  const { latestPrice, forecast, loading, error } = useDashboardData();

  // Determine black swan warning
  const isBlackSwan = forecast
    ? Math.abs(forecast.news_adjustment_pct) > 5 || forecast.confidence < 0.3
    : false;

  return (
    <div className="dashboard-container">
      <Header
        latestPrice={latestPrice}
        forecast={forecast}
        loading={loading}
        isBlackSwan={isBlackSwan}
      />

      {error && !latestPrice && (
        <div className="dashboard-global-error fade-in" style={{ gridColumn: '1 / -1' }}>
          <div className="error-fallback-partial">
            <div className="error-fallback-icon">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="10" cy="10" r="8.5" />
                <line x1="7" y1="7" x2="13" y2="13" />
                <line x1="13" y1="7" x2="7" y2="13" />
              </svg>
            </div>
            <p className="error-fallback-title">대시보드 데이터를 불러올 수 없습니다</p>
            <p className="error-fallback-module">{error.message}</p>
            <p className="error-fallback-module" style={{ marginTop: '4px' }}>
              백엔드 서버가 실행 중인지 확인해 주세요.
            </p>
            <button className="error-retry-button" onClick={() => window.location.reload()}>
              새로고침
            </button>
          </div>
        </div>
      )}

      {/* Progressive loading: each widget manages its own loading/error state independently */}
      <main className="dashboard-chart fade-in">
        <ErrorBoundary moduleName="Price Chart">
          <PriceChart />
        </ErrorBoundary>
      </main>

      <aside className="dashboard-sidebar fade-in" style={{ animationDelay: '0.1s' }}>
        <ErrorBoundary moduleName="Market Factors">
          <FactorGauge />
        </ErrorBoundary>
        <ErrorBoundary moduleName="AI Daily Briefing">
          <AIBriefing />
        </ErrorBoundary>
      </aside>

      <footer className="dashboard-news fade-in" style={{ animationDelay: '0.2s' }}>
        <ErrorBoundary moduleName="News Explorer">
          <NewsExplorer />
        </ErrorBoundary>
      </footer>
    </div>
  );
};
