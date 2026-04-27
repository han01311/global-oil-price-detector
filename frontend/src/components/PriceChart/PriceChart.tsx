import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import {
  ResponsiveContainer, ComposedChart, Line, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceDot,
} from 'recharts';
import type { DotProps } from 'recharts';
import { Card } from '../common/Card';
import { Skeleton } from '../common/Skeleton';
import { EmptyState } from '../common/EmptyState';
import { usePriceData, getCategoryColor } from '../../hooks/usePriceData';
import type { ChartDataPoint, NewsMarker, DBNewsMarker } from '../../hooks/usePriceData';
import { useDashboardContext } from '../../context/DashboardContext';
import './PriceChart.css';

type Interval = 'day' | 'week' | 'month' | 'year';
const INTERVALS: { key: Interval; label: string }[] = [
  { key: 'day', label: '일' },
  { key: 'week', label: '주' },
  { key: 'month', label: '월' },
  { key: 'year', label: '년' },
];

function aggregate(data: ChartDataPoint[], iv: Interval): ChartDataPoint[] {
  if (iv === 'day' || data.length === 0) return data;
  const groups = new Map<string, ChartDataPoint[]>();
  for (const d of data) {
    let key: string;
    if (iv === 'week') {
      const dt = new Date(d.date);
      dt.setDate(dt.getDate() - ((dt.getDay() + 6) % 7));
      key = dt.toISOString().split('T')[0];
    } else if (iv === 'month') {
      key = d.date.slice(0, 7);
    } else {
      key = d.date.slice(0, 4);
    }
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(d);
  }
  return Array.from(groups.values()).map(pts => ({ ...pts[pts.length - 1] }));
}

function chg(curr: number | null | undefined, prev: number | null | undefined) {
  if (!curr || !prev) return null;
  const d = curr - prev, p = (d / prev) * 100;
  return { d, p, up: d > 0, dn: d < 0 };
}

const ChartTooltip: React.FC<any> = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="chart-tooltip-content">
      <p className="tooltip-label">{new Date(label).toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' })}</p>
      {d.dubai != null && <p className="tooltip-item" style={{ color: 'var(--color-primary)' }}>Dubai: ${d.dubai?.toFixed(2)}</p>}
      {d.wti != null && <p className="tooltip-item" style={{ color: '#34C759' }}>WTI: ${d.wti?.toFixed(2)}</p>}
      {d.brent != null && <p className="tooltip-item" style={{ color: '#FF9F0A' }}>Brent: ${d.brent?.toFixed(2)}</p>}
      {d.dbArticleCount > 0 && (
        <div className="tooltip-db-news"><span>📰</span> {d.dbArticleCount}건의 기사</div>
      )}
    </div>
  );
};

/* ── Marker dots (Removed Text for Readability) ── */
const NewsDot: React.FC<DotProps & { payload?: NewsMarker; onClick?: any; isHighlighted: boolean; isDimmed: boolean }> = (
  { cx, cy, payload, onClick, isHighlighted, isDimmed }
) => !payload ? null : (
  <g><circle cx={cx} cy={cy} r={isHighlighted ? 8 : 4}
    fill={getCategoryColor(payload.article.category)} stroke="var(--color-bg)" strokeWidth={1.5}
    onClick={() => onClick?.(payload)}
    style={{ cursor: 'pointer', opacity: isDimmed ? 0.3 : 1 }}
  /></g>
);

const DBDot: React.FC<DotProps & { payload?: DBNewsMarker; onClick?: (m: DBNewsMarker) => void; selectedDate: string | null }> = (
  { cx, cy, payload, onClick, selectedDate }
) => {
  if (!payload || !cx || !cy) return null;
  const s = selectedDate === payload.date;
  // Make size slightly vary by count, but remove the text to avoid clutter
  const baseSize = payload.count > 5 ? 5 : 3; 
  const sz = s ? 7 : baseSize;
  return (
    <g onClick={() => onClick?.(payload)} style={{ cursor: 'pointer' }}>
      {s && <circle cx={cx} cy={cy} r={12} fill="none" stroke="rgba(255,159,107,.3)" strokeWidth={2} />}
      <rect x={Number(cx)-sz} y={Number(cy)-sz} width={sz*2} height={sz*2} rx={1}
        fill={s ? '#FF9F6B' : 'rgba(255,159,107,.75)'} stroke="var(--color-bg)" strokeWidth={1}
        opacity={s?1:.7} transform={`rotate(45,${cx},${cy})`} />
    </g>
  );
};

export const PriceChart: React.FC = () => {
  const [interval, setIv] = useState<Interval>('day');
  const { chartData, newsMarkers, dbNewsMarkers, forecast, loading, error } = usePriceData('ALL');
  const { selectedDate, setSelectedDate, highlightedCategory } = useDashboardContext();

  const aggData = useMemo(() => aggregate(chartData, interval), [chartData, interval]);

  const [xStart, setXStart] = useState(0);
  const [xEnd, setXEnd] = useState(0);
  const chartRef = useRef<HTMLDivElement>(null);

  // Sync state for handlers
  const sr = useRef({ s: 0, e: 0, len: 0 });
  useEffect(() => { sr.current = { s: xStart, e: xEnd, len: aggData.length }; }, [xStart, xEnd, aggData.length]);

  useEffect(() => {
    const n = aggData.length;
    if (n === 0) return;
    if (interval === 'day' && n > 180) {
      setXStart(n - 180);
    } else if (interval === 'week' && n > 104) {
      setXStart(n - 104);
    } else {
      setXStart(0);
    }
    setXEnd(Math.max(0, n - 1));
  }, [aggData.length, interval]);

  const visibleData = useMemo(() => {
    if (aggData.length === 0) return [];
    const s = Math.max(0, Math.min(xStart, aggData.length - 1));
    const e = Math.max(s, Math.min(xEnd, aggData.length - 1));
    return aggData.slice(s, e + 1);
  }, [aggData, xStart, xEnd]);

  const yDomain = useMemo((): [number, number] => {
    const v = visibleData.flatMap(d => [d.wti, d.brent, d.dubai].filter((x): x is number => x != null && x !== 0));
    if (!v.length) return [0, 100];
    const mn = Math.min(...v), mx = Math.max(...v), pad = (mx - mn) * 0.08 || 5;
    return [Math.floor((mn - pad) * 100) / 100, Math.ceil((mx + pad) * 100) / 100];
  }, [visibleData]);

  const tsR = useMemo(() => {
    if (!visibleData.length) return { mn: 0, mx: Infinity };
    return { mn: visibleData[0].timestamp, mx: visibleData[visibleData.length - 1].timestamp };
  }, [visibleData]);
  
  const vNews = useMemo(() => newsMarkers.filter(m => m.timestamp >= tsR.mn && m.timestamp <= tsR.mx), [newsMarkers, tsR]);
  const vDB = useMemo(() => dbNewsMarkers.filter(m => m.timestamp >= tsR.mn && m.timestamp <= tsR.mx), [dbNewsMarkers, tsR]);
  const isZoomed = xStart > 0 || xEnd < aggData.length - 1;

  const priceInfo = useMemo(() => {
    if (chartData.length < 2) return null;
    const l = chartData[chartData.length - 1], p = chartData[chartData.length - 2];
    return { wti: { v: l.wti, c: chg(l.wti, p.wti) }, brent: { v: l.brent, c: chg(l.brent, p.brent) }, dubai: { v: l.dubai, c: chg(l.dubai, p.dubai) } };
  }, [chartData]);

  // ── Mouse Wheel Zoom ──
  const handleWheel = useCallback((e: React.WheelEvent) => {
    // Stop scrolling the page if we are zooming the chart
    if (e.deltaY !== 0) {
      const { s, e: xe, len } = sr.current;
      if (len === 0) return;
      const rect = e.currentTarget.getBoundingClientRect();
      const rel = Math.max(0, Math.min(1, (e.clientX - rect.left - 10) / (rect.width - 60)));
      const cur = xe - s, f = e.deltaY > 0 ? 1.15 : 0.87;
      const nr = Math.max(3, Math.min(len - 1, Math.round(cur * f)));
      const c = s + rel * cur;
      let ns = Math.round(c - rel * nr), ne = ns + nr;
      if (ns < 0) { ne -= ns; ns = 0; }
      if (ne >= len) { ns -= ne - len + 1; ne = len - 1; }
      setXStart(Math.max(0, ns));
      setXEnd(ne);
    }
  }, []);

  // Use a passive=false event listener for wheel to allow preventDefault
  useEffect(() => {
    const el = chartRef.current;
    if (!el) return;
    const preventScroll = (e: WheelEvent) => e.preventDefault();
    el.addEventListener('wheel', preventScroll, { passive: false });
    return () => el.removeEventListener('wheel', preventScroll);
  }, []);

  // ── Drag Pan ──
  const dragState = useRef({ isDragging: false, startX: 0, s: 0, e: 0 });
  const [isDragging, setIsDragging] = useState(false);

  const handlePointerDown = (e: React.PointerEvent) => {
    dragState.current = { isDragging: true, startX: e.clientX, s: sr.current.s, e: sr.current.e };
    setIsDragging(true);
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const handlePointerMove = (e: React.PointerEvent) => {
    if (!dragState.current.isDragging) return;
    const dx = e.clientX - dragState.current.startX;
    const w = e.currentTarget.getBoundingClientRect().width;
    const rng = dragState.current.e - dragState.current.s;
    const shift = Math.round(-dx / w * rng * 1.5);
    
    let ns = dragState.current.s + shift, ne = dragState.current.e + shift;
    const len = sr.current.len;
    if (ns < 0) { ne -= ns; ns = 0; }
    if (ne >= len) { ns -= ne - len + 1; ne = len - 1; }
    setXStart(Math.max(0, ns)); setXEnd(ne);
  };
  const handlePointerUp = (e: React.PointerEvent) => {
    dragState.current.isDragging = false;
    setIsDragging(false);
    e.currentTarget.releasePointerCapture(e.pointerId);
  };

  const resetZoom = useCallback(() => { setXStart(0); setXEnd(aggData.length - 1); }, [aggData.length]);
  
  // ── Click Chart to View News ──
  const handleChartClick = (e: any) => {
    if (e && e.activePayload && e.activePayload.length > 0) {
      const data = e.activePayload[0].payload;
      if (data && data.date) {
        setSelectedDate(data.date);
        setTimeout(() => document.querySelector('.news-explorer-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
      }
    }
  };

  const upT = forecast ? forecast.estimated_7d > forecast.current_price : true;
  const cc = (c: ReturnType<typeof chg>) => !c ? '' : c.up ? 'chg-up' : c.dn ? 'chg-down' : '';
  const cs = (c: ReturnType<typeof chg>) => c?.up ? '+' : '';

  const renderChart = () => {
    if (loading) return <Skeleton height="340px" />;
    if (error) return <div className="error-fallback-partial"><p className="error-fallback-title">차트 로드 실패</p><button className="error-retry-button" onClick={() => window.location.reload()}>재시도</button></div>;
    if (chartData.length === 0) return <EmptyState icon="chart" title="유가 데이터 없음" description="잠시 후 다시 시도해 주세요." />;

    return (
      <div 
        className="chart-container" 
        ref={chartRef} 
        style={{ cursor: isDragging ? 'grabbing' : 'crosshair' }}
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <div className="chart-wrapper">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={visibleData} margin={{ top: 10, right: 55, left: 10, bottom: 30 }} onClick={handleChartClick}>
              <defs>
                <linearGradient id="fc-bull" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="var(--color-bull)" stopOpacity={0.2}/><stop offset="95%" stopColor="var(--color-bull)" stopOpacity={0}/></linearGradient>
                <linearGradient id="fc-bear" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="var(--color-bear)" stopOpacity={0.2}/><stop offset="95%" stopColor="var(--color-bear)" stopOpacity={0}/></linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="timestamp" stroke="var(--color-text-muted)" fontSize={11} axisLine={false} tickLine={false} dy={15} minTickGap={50}
                tickFormatter={(t) => {
                  const d = new Date(t);
                  if (interval === 'year') return d.getFullYear().toString();
                  if (interval === 'month') return `${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,'0')}`;
                  return d.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' });
                }}
              />
              <YAxis orientation="right" domain={yDomain} stroke="var(--color-text-muted)" fontSize={11} axisLine={false} tickLine={false} dx={5}
                tickFormatter={(v) => `$${Number(v).toFixed(2)}`}
              />
              <Tooltip content={<ChartTooltip />} isAnimationActive={false} />
              <Line type="monotone" dataKey="dubai" stroke="var(--color-primary)" strokeWidth={1.5} dot={false} connectNulls isAnimationActive={false} />
              <Line type="monotone" dataKey="wti" stroke="#34C759" strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
              <Line type="monotone" dataKey="brent" stroke="#FF9F0A" strokeWidth={1.5} dot={false} connectNulls isAnimationActive={false} />
              <Line type="monotone" dataKey="forecastLine" stroke={upT ? 'var(--color-bull)' : 'var(--color-bear)'} strokeWidth={2} strokeDasharray="5 5" dot={false} />
              <Area type="monotone" dataKey="forecastBand" fill={`url(#${upT?'fc-bull':'fc-bear'})`} stroke="none" />

              {interval === 'day' && vDB.map((m, i) => (
                <ReferenceDot key={`d${i}`} x={m.timestamp} y={m.value} ifOverflow="extendDomain"
                  shape={<DBDot payload={m} onClick={() => {}} selectedDate={selectedDate} />} />
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  };

  return (
    <Card title="Price Chart" className="price-chart-card">
      {priceInfo && (
        <div className="price-change-header">
          {[
            { l: 'WTI', v: priceInfo.wti.v, c: priceInfo.wti.c, clr: '#34C759' },
            { l: 'Brent', v: priceInfo.brent.v, c: priceInfo.brent.c, clr: '#FF9F0A' },
            { l: 'Dubai', v: priceInfo.dubai.v, c: priceInfo.dubai.c, clr: 'var(--color-primary)' },
          ].map(it => it.v && (
            <div key={it.l} className="price-change-item">
              <span className="pci-dot" style={{ background: it.clr }} />
              <span className="pci-label">{it.l}</span>
              <span className="pci-price">${it.v.toFixed(2)}</span>
              {it.c && <span className={`pci-change ${cc(it.c)}`}>{cs(it.c)}${Math.abs(it.c.d).toFixed(2)} ({cs(it.c)}{Math.abs(it.c.p).toFixed(2)}%)</span>}
            </div>
          ))}
        </div>
      )}

      <div className="price-chart-controls">
        <div className="interval-selector">
          {INTERVALS.map(iv => (
            <button key={iv.key} className={interval === iv.key ? 'active' : ''} onClick={() => setIv(iv.key)}>{iv.label}</button>
          ))}
        </div>
        <div className="controls-right">
          {isZoomed && <button className="zoom-reset-btn" onClick={resetZoom}>⟲ 전체보기</button>}
          {vDB.length > 0 && <div className="chart-legend-hint"><span className="legend-diamond">◆</span> 기사 보유 날짜</div>}
        </div>
      </div>

      {isZoomed && visibleData.length > 0 && (
        <div className="zoom-range-indicator">
          <span>{visibleData[0].date} ~ {visibleData[visibleData.length - 1].date} ({visibleData.length}건)</span>
          <span className="zoom-hint">드래그: 좌우 이동 · 스크롤: 확대/축소 (차트 클릭 시 기사 검색)</span>
        </div>
      )}

      {renderChart()}
    </Card>
  );
};
