import React from 'react';
import { Header } from './Header';
import { PriceChart } from '../PriceChart/PriceChart';
import { FactorGauge } from '../FactorGauge/FactorGauge';
import { AIBriefing } from '../Briefing/AIBriefing';
import { NewsExplorer } from '../NewsExplorer/NewsExplorer';
import { useDashboardData } from '../../hooks/useDashboardData';
import './Dashboard.css';
import { Card } from '../common/Card';

export const Dashboard: React.FC = () => {
  const { latestPrice, forecast, loading, error } = useDashboardData();

  if (error) {
    return (
      <Card title="Error">
        <div style={{ color: 'var(--color-error)' }}>
          <h2>Failed to load dashboard data</h2>
          <p>{error.message}</p>
        </div>
      </Card>
    );
  }

  return (
    <div className="dashboard-container">
      <Header latestPrice={latestPrice} forecast={forecast} loading={loading} />
      
      <main className="dashboard-chart">
        <PriceChart />
      </main>

      <aside className="dashboard-sidebar">
        <FactorGauge />
        <AIBriefing />
      </aside>

      <footer className="dashboard-news">
        <NewsExplorer />
      </footer>
    </div>
  );
};
