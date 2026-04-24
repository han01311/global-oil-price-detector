import React from 'react';
import { Header } from './Header';
import { PriceChart } from '../PriceChart/PriceChart';
import { FactorGauge } from '../FactorGauge/FactorGauge';
import { AIBriefing } from '../Briefing/AIBriefing';
import { NewsExplorer } from '../NewsExplorer/NewsExplorer';
import { useDashboardData } from '../../hooks/useDashboardData';
import './Dashboard.css';
import { Card } from '../common/Card';
import { Skeleton } from '../common/Skeleton';

export const Dashboard: React.FC = () => {
  const { latestPrice, forecast, loading, error } = useDashboardData();

  if (loading) {
    return (
      <div className="dashboard-container">
        <Header latestPrice={null} forecast={null} loading={true} />
        <main className="dashboard-chart">
          <Card title="Price Chart"><Skeleton height="400px" /></Card>
        </main>
        <aside className="dashboard-sidebar">
          <Card title="Market Factors"><Skeleton height="240px" /></Card>
          <Card title="AI Daily Briefing"><Skeleton height="300px" /></Card>
        </aside>
        <footer className="dashboard-news">
          <Card title="News Explorer"><Skeleton height="200px" /></Card>
        </footer>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard-container">
        <Header latestPrice={null} forecast={null} loading={false} />
        <main className="dashboard-chart" style={{ gridColumn: '1 / -1' }}>
          <Card title="Error">
            <div style={{ color: 'var(--color-error)' }}>
              <h2>Failed to load dashboard data</h2>
              <p>{error.message}</p>
              <p style={{ marginTop: '1rem', color: 'var(--color-text-secondary)'}}>
                Please ensure the backend server is running and accessible.
              </p>
            </div>
          </Card>
        </main>
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      <Header latestPrice={latestPrice} forecast={forecast} loading={loading} />
      
      <main className="dashboard-chart fade-in">
        <PriceChart />
      </main>

      <aside className="dashboard-sidebar fade-in" style={{ animationDelay: '0.1s' }}>
        <FactorGauge />
        <AIBriefing />
      </aside>

      <footer className="dashboard-news fade-in" style={{ animationDelay: '0.2s' }}>
        <NewsExplorer />
      </footer>
    </div>
  );
};
