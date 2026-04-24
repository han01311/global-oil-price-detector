import React, { useState } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceDot,
} from 'recharts';
import { Card } from '../common/Card';
import { Skeleton } from '../common/Skeleton';
import { usePriceData, Period, getCategoryColor } from '../../hooks/usePriceData';
import { Badge } from '../common/Badge';
import './PriceChart.css';

const periods: Period[] = ['1M', '3M', '6M', '1Y', 'ALL'];

const CustomTooltip: React.FC<any> = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    const newsDot = payload.find(p => p.dataKey === 'value' && p.payload.article);

    return (
      <div className="chart-tooltip-content">
        <p className="tooltip-label">{new Date(label).toLocaleDateString()}</p>
        {data.wti && <p className="tooltip-item" style={{ color: 'var(--color-bull)' }}>WTI: ${data.wti.toFixed(2)}</p>}
        {data.brent && <p className="tooltip-item" style={{ color: 'var(--color-bear)' }}>Brent: ${data.brent.toFixed(2)}</p>}
        {data.forecastLine && <p className="tooltip-item">Forecast: ${data.forecastLine.toFixed(2)}</p>}
        {newsDot && (
          <div className="tooltip-news-item">
            <Badge category={newsDot.payload.article.category as any} />
            <span>{newsDot.payload.article.article.title}</span>
            <p>Impact: {newsDot.payload.article.impact_score}</p>
          </div>
        )}
      </div>
    );
  }
  return null;
};

export const PriceChart: React.FC = () => {
  const [activePeriod, setActivePeriod] = useState<Period>('6M');
  const { chartData, newsMarkers, forecast, loading, error } = usePriceData(activePeriod);

  const isUpwardTrend = forecast ? forecast.estimated_7d > forecast.current_price : true;
  const forecastColorId = isUpwardTrend ? 'forecast-bull' : 'forecast-bear';
  const forecastStrokeColor = isUpwardTrend ? 'var(--color-bull)' : 'var(--color-bear)';

  const renderChart = () => {
    if (loading) {
      return <Skeleton height="400px" />;
    }
    if (error) {
      return <p style={{ color: 'var(--color-error)' }}>Error loading chart data: {error.message}</p>;
    }
    if (chartData.length === 0) {
      return <p>No data available for the selected period.</p>;
    }

    const yDomain = [ 'dataMin - 5', 'dataMax + 5' ];

    return (
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
          <defs>
            <linearGradient id="forecast-bull" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--color-bull)" stopOpacity={0.2}/>
              <stop offset="95%" stopColor="var(--color-bull)" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="forecast-bear" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--color-bear)" stopOpacity={0.2}/>
              <stop offset="95%" stopColor="var(--color-bear)" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis 
            dataKey="timestamp"
            tickFormatter={(unixTime) => new Date(unixTime).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            stroke="var(--color-text-muted)"
            fontSize={12}
          />
          <YAxis 
            orientation="right" 
            domain={yDomain}
            tickFormatter={(value) => `$${value}`}
            stroke="var(--color-text-muted)"
            fontSize={12}
          />
          <Tooltip content={<CustomTooltip />} />
          
          <Line type="monotone" dataKey="wti" stroke="var(--color-bull)" strokeWidth={2} dot={false} name="WTI" />
          <Line type="monotone" dataKey="brent" stroke="var(--color-bear)" strokeWidth={2} dot={false} name="Brent" />
          
          <Line type="monotone" dataKey="forecastLine" stroke={forecastStrokeColor} strokeWidth={2} strokeDasharray="5 5" dot={false} name="Forecast" />
          <Area type="monotone" dataKey="forecastBand" fill={`url(#${forecastColorId})`} stroke={false} name="Forecast Range" />

          {newsMarkers.map((marker, index) => (
            <ReferenceDot 
              key={index} 
              x={marker.timestamp} 
              y={marker.value} 
              r={5} 
              fill={getCategoryColor(marker.article.category)}
              stroke="var(--color-bg)"
              strokeWidth={1}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    );
  };

  return (
    <Card title="Price Chart" className="price-chart-card">
      <div className="price-chart-controls">
        <div className="period-selector">
          {periods.map(p => (
            <button 
              key={p} 
              className={activePeriod === p ? 'active' : ''}
              onClick={() => setActivePeriod(p)}
            >
              {p}
            </button>
          ))}
        </div>
      </div>
      {renderChart()}
    </Card>
  );
};