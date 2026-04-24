import React from 'react';
import { Card } from '../common/Card';

export const PriceChart: React.FC = () => {
  return (
    <Card title="Price Chart" className="price-chart-card">
      <div style={{ height: '400px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p>Price Chart will be implemented here.</p>
      </div>
    </Card>
  );
};
