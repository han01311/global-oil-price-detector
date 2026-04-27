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
import type { Period, NewsMarker, DBNewsMarker } from '../../hooks/usePriceData';
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
        {data.dbArticleCount && (
          <div className="tooltip-db-news">
            <span className="tooltip-db-icon">📰</span>
            <span>{data.dbArticleCount}건의 기사</span>
          </div>
        )}
        {data.article && (
          <div className="tooltip-news-item">
            <Badge category={data.article.category as any} />
            <span>{data.article.article.title}</span>
            <div className="tooltip-news-impact">
              {data.article.impact_by_crude ? (
                Object.entries(data.article.impact_by_crude).map(([crudeType, impact]: [string, any]) => (
                  <span key={crudeType} className="tooltip-crude-impact">
                    {crudeType.charAt(0).toUpperCase() + crudeType.slice(1)}: 
                    <span className={impact.score > 0 ? 'tooltip-bull' : impact.score < 0 ? 'tooltip-bear' : ''}>
                      {impact.score > 0 ? '+' : ''}{impact.score}
                    </span>
                  </span>
                ))
              ) : (
                <span>
                  Impact: <span className={data.article.impact_score > 0 ? 'tooltip-bull' : data.article.impact_score < 0 ? 'tooltip-bear' : ''}>
                    {data.article.impact_score > 0 ? '+' : ''}{data.article.impact_score}
                  </span>
                </span>
              )}
            </div>
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

// DB 기사 마커 — 작은 다이아몬드 점
interface DBNewsDotProps extends DotProps {
  payload?: DBNewsMarker;
  onClick?: (marker: DBNewsMarker) => void;
  selectedDate: string | null;
}

const DBNewsDot: React.FC<DBNewsDotProps> = (props) => {
  const { cx, cy, payload, onClick, selectedDate } = props;
  if (!payload || !cx || !cy) return null;

  const isSelected = selectedDate === payload.date;
  const size = isSelected ? 7 : 4;
  const opacity = isSelected ? 1 : 0.7;

  return (
    <g
      onClick={() => onClick?.(payload)}
      style={{ cursor: 'pointer' }}
    >
      {/* 외곽 글로우 (선택 시) */}
      {isSelected && (
        <circle
          cx={cx}
          cy={cy}
          r={12}
          fill="none"
          stroke="rgba(255, 159, 107, 0.3)"
          strokeWidth={2}
        />
      )}
      {/* 다이아몬드 형태 */}
      <rect
        x={Number(cx) - size}
        y={Number(cy) - size}
        width={size * 2}
        height={size * 2}
        rx={2}
        fill={isSelected ? '#FF9F6B' : 'rgba(255, 159, 107, 0.75)'}
        stroke="var(--color-bg)"
        strokeWidth={1.5}
        opacity={opacity}
        transform={`rotate(45, ${cx}, ${cy})`}
        style={{ transition: 'all 0.2s ease' }}
      />
      {/* 기사 수 (3건 이상이면 표시) */}
      {payload.count >= 3 && (
        <text
          x={Number(cx)}
          y={Number(cy) - size - 6}
          textAnchor="middle"
          fontSize={9}
          fontWeight={600}
          fill="rgba(255, 159, 107, 0.9)"
        >
          {payload.count}
        </text>
      )}
    </g>
  );
};

export const PriceChart: React.FC = () => {
  const [activePeriod, setActivePeriod] = useState<Period>('6M');
  const { chartData, newsMarkers, dbNewsMarkers, forecast, loading, error } = usePriceData(activePeriod);
  const { selectedDate, setSelectedDate, highlightedCategory } = useDashboardContext();

  const handleMarkerClick = (marker: NewsMarker) => {
    const dateStr = new Date(marker.timestamp).toISOString().split('T')[0];
    setSelectedDate(dateStr);
  };

  const handleDBMarkerClick = (marker: DBNewsMarker) => {
    setSelectedDate(marker.date);
    // 부드럽게 News Explorer로 스크롤
    setTimeout(() => {
      document.querySelector('.news-explorer-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  };

  const isUpwardTrend = forecast ? forecast.estimated_7d > forecast.current_price : true;
  const forecastColorId = isUpwardTrend ? 'forecast-bull' : 'forecast-bear';
  const forecastStrokeColor = isUpwardTrend ? 'var(--color-bull)' : 'var(--color-bear)';

  const renderChart = () => {
    if (loading) {
      return <Skeleton height="340px" />;
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
    const yDomain = ['auto', 'auto'];

    return (
      <div className="chart-container">
        <div className="chart-wrapper">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 10, right: 40, left: 40, bottom: 40 }}>
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
              tickFormatter={(unixTime) => new Date(unixTime).toLocaleDateString('ko-KR', { year: 'numeric', month: 'short', day: 'numeric' })}
              stroke="var(--color-text-muted)"
              fontSize={11}
              axisLine={false}
              tickLine={false}
              dy={20}
              minTickGap={30}
            />
            <YAxis 
              orientation="right" 
              domain={yDomain}
              tickFormatter={(value) => `$${value}`}
              stroke="var(--color-text-muted)"
              fontSize={11}
              axisLine={false}
              tickLine={false}
              dx={10}
            />
          <Tooltip content={<CustomTooltip />} />
          
          <Line type="monotone" dataKey="dubai" stroke="var(--color-primary)" strokeWidth={2} dot={false} name="Dubai" connectNulls={true} />
          <Line type="monotone" dataKey="wti" stroke="var(--color-bull)" strokeWidth={2} dot={false} name="WTI" connectNulls={true} />
          <Line type="monotone" dataKey="brent" stroke="var(--color-bear)" strokeWidth={2} dot={false} name="Brent" connectNulls={true} />
          
          <Line type="monotone" dataKey="forecastLine" stroke={forecastStrokeColor} strokeWidth={2} strokeDasharray="5 5" dot={false} name="Forecast" />
          <Area type="monotone" dataKey="forecastBand" fill={`url(#${forecastColorId})`} stroke="none" name="Forecast Range" />

          {/* DB 기사 마커 (다이아몬드) */}
          {dbNewsMarkers.map((marker, index) => (
            <ReferenceDot 
              key={`db-${index}`} 
              x={marker.timestamp} 
              y={marker.value} 
              ifOverflow="extendDomain"
              shape={
                <DBNewsDot 
                  payload={marker} 
                  onClick={handleDBMarkerClick}
                  selectedDate={selectedDate}
                />
              }
            />
          ))}

          {/* Classified 뉴스 마커 (원형) */}
          {newsMarkers.map((marker, index) => (
            <ReferenceDot 
              key={`news-${index}`} 
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
        </div>
      </div>
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
        {dbNewsMarkers.length > 0 && (
          <div className="chart-legend-hint">
            <span className="legend-diamond">◆</span>
            <span>기사 보유 ({dbNewsMarkers.length}일)</span>
          </div>
        )}
      </div>
      {renderChart()}
    </Card>
  );
};
