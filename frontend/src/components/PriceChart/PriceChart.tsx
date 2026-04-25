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
  ReferenceDot
} from 'recharts';
import type { DotProps } from 'recharts';
import { Card } from '../common/Card';
import { Skeleton } from '../common/Skeleton';
import { EmptyState } from '../common/EmptyState';
import { usePriceData, getCategoryColor } from '../../hooks/usePriceData';
import type { Period, NewsMarker } from '../../hooks/usePriceData';
import { Badge } from '../common/Badge';
import { useDashboardContext } from '../../context/DashboardContext';
import './PriceChart.css';

const periods: Period[] = ['1M', '3M', '6M', '1Y', 'ALL'];

const CustomTooltip: React.FC<any> = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    
    return (
      <div className="chart-tooltip-content">
        <p className="tooltip-label">{new Date(label).toLocaleDateString()}</p>
        {data.dubai && <p className="tooltip-item" style={{ color: 'var(--color-primary)' }}>Dubai: ${data.dubai.toFixed(2)}</p>}
        {data.wti && <p className="tooltip-item" style={{ color: 'var(--color-bull)' }}>WTI: ${data.wti.toFixed(2)}</p>}
        {data.brent && <p className="tooltip-item" style={{ color: 'var(--color-bear)' }}>Brent: ${data.brent.toFixed(2)}</p>}
        {data.forecastLine && <p className="tooltip-item">Forecast: ${data.forecastLine.toFixed(2)}</p>}
        {data.article && (
          <div className="tooltip-news-item">
            <Badge category={data.article.category as any} />
            <span>{data.article.article.title}</span>
            <p className="tooltip-news-impact">
              Impact: <span className={data.article.impact_score > 0 ? 'tooltip-bull' : data.article.impact_score < 0 ? 'tooltip-bear' : ''}>
                {data.article.impact_score > 0 ? '+' : ''}{data.article.impact_score}
              </span>
            </p>
            {data.article.impact_summary && (
              <p className="tooltip-news-snippet">{data.article.impact_summary}</p>
            )}
          </div>
        )}
      </div>
    );
  }
  return null;
};

interface CustomDotProps extends DotProps {
  payload?: NewsMarker;
  onClick?: any;
  isHighlighted: boolean;
  isDimmed: boolean;
}

const CustomNewsDot: React.FC<CustomDotProps> = (props) => {
  const { cx, cy, payload, onClick, isHighlighted, isDimmed } = props;

  if (!payload) return null;

  const handleClick = () => {
    if (onClick && payload) {
      onClick(payload);
    }
  };

  return (
    <g>
      <circle
        cx={cx}
        cy={cy}
        r={isHighlighted ? 8 : 5}
        fill={getCategoryColor(payload.article.category)}
        stroke="var(--color-bg)"
        strokeWidth={2}
        onClick={handleClick}
        style={{
          cursor: 'pointer',
          opacity: isDimmed ? 0.3 : 1,
          transition: 'r 0.2s ease, opacity 0.2s ease',
        }}
      />
    </g>
  );
};

export const PriceChart: React.FC = () => {
  const [activePeriod, setActivePeriod] = useState<Period>('6M');
  const { chartData, newsMarkers, forecast, loading, error } = usePriceData(activePeriod);
  const { setSelectedDate, highlightedCategory } = useDashboardContext();

  const handleMarkerClick = (marker: NewsMarker) => {
    const dateStr = new Date(marker.timestamp).toISOString().split('T')[0];
    setSelectedDate(dateStr);
  };

  const isUpwardTrend = forecast ? forecast.estimated_7d > forecast.current_price : true;
  const forecastColorId = isUpwardTrend ? 'forecast-bull' : 'forecast-bear';
  const forecastStrokeColor = isUpwardTrend ? 'var(--color-bull)' : 'var(--color-bear)';

  const renderChart = () => {
    if (loading) {
      return <Skeleton height="400px" />;
    }
    if (error) {
      return (
        <div className="error-fallback-partial">
          <div className="error-fallback-icon">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="10" cy="10" r="8.5" />
              <line x1="7" y1="7" x2="13" y2="13" />
              <line x1="13" y1="7" x2="7" y2="13" />
            </svg>
          </div>
          <p className="error-fallback-title">차트 데이터를 불러올 수 없습니다</p>
          <p className="error-fallback-module">{error.message}</p>
          <button className="error-retry-button" onClick={() => window.location.reload()}>
            재시도
          </button>
        </div>
      );
    }
    if (chartData.length === 0) {
      return <EmptyState icon="chart" title="선택한 기간에 유가 데이터가 없습니다" description="다른 기간을 선택해 주세요." />;
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
          
          <Line type="monotone" dataKey="dubai" stroke="var(--color-primary)" strokeWidth={2} dot={false} name="Dubai" connectNulls={true} />
          <Line type="monotone" dataKey="wti" stroke="var(--color-bull)" strokeWidth={2} dot={false} name="WTI" connectNulls={true} />
          <Line type="monotone" dataKey="brent" stroke="var(--color-bear)" strokeWidth={2} dot={false} name="Brent" connectNulls={true} />
          
          <Line type="monotone" dataKey="forecastLine" stroke={forecastStrokeColor} strokeWidth={2} strokeDasharray="5 5" dot={false} name="Forecast" />
          <Area type="monotone" dataKey="forecastBand" fill={`url(#${forecastColorId})`} stroke="none" name="Forecast Range" />

          {newsMarkers.map((marker, index) => (
            <ReferenceDot 
              key={index} 
              x={marker.timestamp} 
              y={marker.value} 
              ifOverflow="extendDomain"
              shape={
                <CustomNewsDot 
                  payload={marker} 
                  onClick={handleMarkerClick}
                  isHighlighted={highlightedCategory === marker.article.category}
                  isDimmed={!!highlightedCategory && highlightedCategory !== marker.article.category}
                />
              }
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
