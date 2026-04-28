import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import {
  ResponsiveContainer, ComposedChart, Line, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, Bar, LabelList
} from 'recharts';

import { Card } from '../common/Card';
import { Skeleton } from '../common/Skeleton';
import { EmptyState } from '../common/EmptyState';
import { usePriceData } from '../../hooks/usePriceData';
import type { ChartDataPoint } from '../../hooks/usePriceData';
import { useDashboardContext } from '../../context/DashboardContext';
import './PriceChart.css';

const CustomCursor = (props: any) => {
  if (!props || props.points == null || props.points.length === 0) return null;
  const { points, height, payload } = props;
  const x = points[0].x;
  const y = points[0].y;
  
  const handleCursorClick = () => {
    if (payload && payload.length > 0 && props.onCursorClick) {
      props.onCursorClick(payload[0].payload);
    }
  };

  return (
    <g style={{ cursor: 'pointer' }} onClick={handleCursorClick}>
      <line x1={x} y1={y} x2={x} y2={y + height} stroke="rgba(255,255,255,0.7)" strokeWidth={1} strokeDasharray="3 3" />
      <rect x={x - 15} y={y} width={30} height={height} fill="transparent" style={{ pointerEvents: 'auto' }} />
    </g>
  );
};

type Interval = 'day' | 'week' | 'month' | 'year';
const INTERVALS: { key: Interval; label: string }[] = [
  { key: 'day', label: '일' },
  { key: 'week', label: '주' },
  { key: 'month', label: '월' },
  { key: 'year', label: '년' },
];

function aggregate(data: ChartDataPoint[], iv: Interval, rawCounts?: Record<string, number>): ChartDataPoint[] {
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
  return Array.from(groups.entries()).map(([k, pts]) => {
    const first = pts[0];
    const last = pts[pts.length - 1];
    
    let sumCount = 0;
    if (rawCounts) {
      // iterate through dates from first to last using string comparison
      const startStr = first.date;
      const endStr = last.date;
      for (const [dateStr, count] of Object.entries(rawCounts)) {
        if (dateStr >= startStr && dateStr <= endStr) {
          sumCount += count;
        }
      }
    } else {
      sumCount = pts.reduce((acc, curr) => acc + (curr.dbArticleCount || 0), 0);
    }

    return { 
      ...last, 
      dbArticleCount: sumCount || undefined, 
      filterDate: k,
      groupStartDate: first.date,
      groupEndDate: last.date
    };
  });
}

function chg(curr: number | null | undefined, prev: number | null | undefined) {
  if (!curr || !prev) return null;
  const d = curr - prev, p = (d / prev) * 100;
  return { d, p, up: d > 0, dn: d < 0 };
}

const ChartTooltip: React.FC<any> = ({ active, payload, label, interval }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="chart-tooltip-content">
      <p className="tooltip-label">{new Date(label).toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' })}</p>
      {d.dubai != null && <p className="tooltip-item" style={{ color: 'var(--color-primary)' }}>Dubai: ${d.dubai?.toFixed(2)}</p>}
      {d.wti != null && <p className="tooltip-item" style={{ color: '#34C759' }}>WTI: ${d.wti?.toFixed(2)}</p>}
      {d.brent != null && <p className="tooltip-item" style={{ color: '#FF9F0A' }}>Brent: ${d.brent?.toFixed(2)}</p>}
      {d.dbArticleCount && d.dbArticleCount > 0 && (
        <>
          <div className="tooltip-db-news">
            <span style={{ fontSize: '13px' }}>📰</span> 관련 기사 {d.dbArticleCount}건 수집됨
          </div>
          {interval !== 'day' && d.groupStartDate && d.groupEndDate && (
            <div className="tooltip-news-range" style={{ fontSize: '10px', color: 'var(--color-text-muted)', marginTop: '4px' }}>
              수집 범위: {d.groupStartDate} ~ {d.groupEndDate}
            </div>
          )}
        </>
      )}
    </div>
  );
};

/* ── Marker dots (NewsDot for single articles is kept if needed, but db counts are now bars) ── */

export const PriceChart: React.FC = () => {
  const [interval, setIv] = useState<Interval>('day');
  const { chartData, forecast, loading, error, rawNewsCounts } = usePriceData('ALL');
  const { setSelectedDate, setSelectedDateRange } = useDashboardContext();

  const aggData = useMemo(() => aggregate(chartData, interval, rawNewsCounts), [chartData, interval, rawNewsCounts]);

  const [xStart, setXStart] = useState(0);
  const [xEnd, setXEnd] = useState(0);
  const chartRef = useRef<HTMLDivElement>(null);

  // Sync state for handlers
  const sr = useRef({ s: 0, e: 0, len: 0 });
  useEffect(() => { sr.current = { s: xStart, e: xEnd, len: aggData.length }; }, [xStart, xEnd, aggData.length]);

  useEffect(() => {
    const n = aggData.length;
    if (n === 0) return;
    
    // 일/주/월 클릭 시 최신 100개의 데이터를 기본으로 보여줌 (년은 100개가 안 되므로 전체 표시)
    if (n > 100) {
      setXStart(n - 100);
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

  const [vis, setVis] = useState({ dubai: true, wti: true, brent: true, news: true });
  const toggleVis = (k: keyof typeof vis) => setVis(p => ({ ...p, [k]: !p[k] }));

  const yDomain = useMemo((): [number, number] => {
    const v = visibleData.flatMap(d => [
      vis.wti ? d.wti : null, 
      vis.brent ? d.brent : null, 
      vis.dubai ? d.dubai : null
    ].filter((x): x is number => x != null && x !== 0));
    if (!v.length) return [0, 100];
    const mn = Math.min(...v), mx = Math.max(...v), pad = (mx - mn) * 0.08 || 5;
    return [Math.floor((mn - pad) * 100) / 100, Math.ceil((mx + pad) * 100) / 100];
  }, [visibleData, vis]);

  const tsR = useMemo(() => {
    if (!visibleData.length) return { mn: 0, mx: Infinity };
    return { mn: visibleData[0].timestamp, mx: visibleData[visibleData.length - 1].timestamp };
  }, [visibleData]);
  
  const maxNewsCount = useMemo(() => {
    let m = 0;
    for (const d of visibleData) { if (d.dbArticleCount && d.dbArticleCount > m) m = d.dbArticleCount; }
    return m || 10;
  }, [visibleData]);
  const isZoomed = xStart > 0 || xEnd < aggData.length - 1;

  const priceInfo = useMemo(() => {
    if (chartData.length < 2) return null;
    const l = chartData[chartData.length - 1], p = chartData[chartData.length - 2];
    return { wti: { v: l.wti, c: chg(l.wti, p.wti) }, brent: { v: l.brent, c: chg(l.brent, p.brent) }, dubai: { v: l.dubai, c: chg(l.dubai, p.dubai) } };
  }, [chartData]);

  // ── Mouse Wheel Zoom (Native Event for e.preventDefault) ──
  useEffect(() => {
    const el = chartRef.current;
    if (!el) return;
    
    let panAcc = 0;

    const handleWheelNative = (e: WheelEvent) => {
      e.preventDefault(); // 페이지 스크롤 완벽 차단
      e.stopPropagation();
      
      const { s, e: xe, len } = sr.current;
      if (len === 0) return;

      if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        // 트랙패드 가로 스크롤 (패닝)
        const w = el.getBoundingClientRect().width;
        const rng = xe - s;
        
        panAcc += e.deltaX;
        const shift = Math.round((panAcc / w) * rng * 1.5);
        
        if (shift !== 0) {
          panAcc -= (shift / (rng * 1.5)) * w; // 이동한 만큼 픽셀 소모
          
          let ns = s + shift, ne = xe + shift;
          if (ns < 0) { ne -= ns; ns = 0; }
          if (ne >= len) { ns -= ne - len + 1; ne = len - 1; }
          
          if (ns !== s || ne !== xe) {
            sr.current.s = Math.max(0, ns);
            sr.current.e = ne;
            setXStart(sr.current.s);
            setXEnd(sr.current.e);
          }
        }
      } else if (e.deltaY !== 0) {
        // 기존 마우스 휠 세로 스크롤 (줌인/줌아웃)
        const rect = el.getBoundingClientRect();
        const rel = Math.max(0, Math.min(1, (e.clientX - rect.left - 10) / (rect.width - 60)));
        const cur = xe - s;
        
        const zoomSensitivity = 0.003;
        const f = Math.exp(Math.abs(e.deltaY) * zoomSensitivity);
        
        let nr = e.deltaY > 0 ? Math.round(cur * f) : Math.round(cur / f);
        
        if (e.deltaY > 0 && nr <= cur) nr = cur + 1; 
        if (e.deltaY < 0 && nr >= cur) nr = cur - 1;
        
        nr = Math.max(5, Math.min(len - 1, nr));
        const c = s + rel * cur;
        let ns = Math.round(c - rel * nr), ne = ns + nr;
        
        if (ns < 0) { ne -= ns; ns = 0; }
        if (ne >= len) { ns -= ne - len + 1; ne = len - 1; }
        
        if (ns !== s || ne !== xe) {
          sr.current.s = Math.max(0, ns);
          sr.current.e = ne;
          setXStart(sr.current.s);
          setXEnd(sr.current.e);
        }
      }
    };
    
    el.addEventListener('wheel', handleWheelNative, { passive: false });
    return () => el.removeEventListener('wheel', handleWheelNative);
  }, [loading]);

  // ── Drag Pan ──
  const dragState = useRef({ isDragging: false, isPanning: false, startX: 0, s: 0, e: 0 });
  const activePayloadRef = useRef<any>(null);

  const handleMouseDown = (e: React.MouseEvent) => {
    dragState.current = { isDragging: true, isPanning: false, startX: e.clientX, s: sr.current.s, e: sr.current.e };
  };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!dragState.current.isDragging) return;
    const dx = e.clientX - dragState.current.startX;
    
    if (!dragState.current.isPanning && Math.abs(dx) > 5) {
      dragState.current.isPanning = true;
      if (chartRef.current) chartRef.current.style.cursor = 'grabbing';
    }
    
    if (!dragState.current.isPanning) return;

    const w = e.currentTarget.getBoundingClientRect().width;
    const rng = dragState.current.e - dragState.current.s;
    const shift = Math.round(-dx / w * rng * 1.5);
    
    let ns = dragState.current.s + shift, ne = dragState.current.e + shift;
    const len = sr.current.len;
    if (ns < 0) { ne -= ns; ns = 0; }
    if (ne >= len) { ns -= ne - len + 1; ne = len - 1; }
    setXStart(Math.max(0, ns)); setXEnd(ne);
  };
  const handleMouseUp = () => {
    dragState.current.isDragging = false;
    dragState.current.isPanning = false;
    if (chartRef.current) chartRef.current.style.cursor = 'crosshair';
  };

  const handleElementClick = (data: any) => {
    if (dragState.current.isPanning) return;
    if (data) {
      if (interval !== 'day' && data.groupStartDate && data.groupEndDate) {
        setSelectedDateRange({ start: data.groupStartDate, end: data.groupEndDate });
      } else if (data.filterDate || data.date) {
        setSelectedDate(data.filterDate || data.date);
      }
      setTimeout(() => document.querySelector('.news-explorer-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
    }
  };

  const handleChartClick = (state: any) => {
    if (dragState.current.isPanning) return;
    if (state && state.activePayload && state.activePayload.length > 0) {
      handleElementClick(state.activePayload[0].payload);
    }
  };



  const handleChartMouseMove = (e: any) => {
    if (e && e.activePayload && e.activePayload.length > 0) {
      activePayloadRef.current = e.activePayload[0].payload;
    }
  };

  const resetZoom = useCallback(() => { setXStart(0); setXEnd(aggData.length - 1); }, [aggData.length]);



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
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ cursor: 'crosshair' }}
      >
        <div className="chart-wrapper">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={visibleData} margin={{ top: 25, right: 20, left: 10, bottom: 10 }} onClick={handleChartClick} onMouseMove={handleChartMouseMove}>
              <defs>
                <linearGradient id="fc-bull" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="var(--color-bull)" stopOpacity={0.2}/><stop offset="95%" stopColor="var(--color-bull)" stopOpacity={0}/></linearGradient>
                <linearGradient id="fc-bear" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="var(--color-bear)" stopOpacity={0.2}/><stop offset="95%" stopColor="var(--color-bear)" stopOpacity={0}/></linearGradient>
              </defs>
              <CartesianGrid vertical={true} stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="timestamp" stroke="var(--color-text-muted)" fontSize={11} axisLine={false} tickLine={false} dy={15} minTickGap={50}
                tickFormatter={(t, index) => {
                  const d = new Date(t);
                  const y = d.getFullYear();
                  const m = d.getMonth() + 1;
                  const day = d.getDate();
                  
                  if (interval === 'year') return y.toString();
                  
                  const spanDays = (tsR.mx - tsR.mn) / (1000 * 60 * 60 * 24);
                  
                  // 1. 아주 넓은 범위 (5년 이상) -> 1월이면 연도, 아니면 YYYY.MM
                  if (spanDays > 365 * 5) {
                    return m === 1 ? y.toString() : `${y}.${String(m).padStart(2, '0')}`;
                  }
                  
                  // 2. 중간 범위 (1년 ~ 5년) -> 1월 눈금이 스킵되더라도 연도를 알 수 있도록 모든 틱에 연도 포함
                  if (spanDays >= 365) {
                    return `${y}.${String(m).padStart(2, '0')}`;
                  }
                  
                  // 3. 좁은 범위 (1년 미만)
                  if (interval === 'day' && spanDays < 90) {
                    // 첫 번째 눈금이거나 연초인 경우 연도 포함
                    if (index === 0 || (m === 1 && day <= 15)) return `${y}.${String(m).padStart(2, '0')}.${String(day).padStart(2, '0')}`;
                    return `${m}.${day}`;
                  }
                  
                  // 그 외 (1년 미만의 주/월 단위)
                  if (index === 0 || m === 1) return `${y}년 ${m}월`;
                  return `${m}월`;
                }}
              />
              <YAxis yAxisId="0" orientation="right" domain={yDomain} stroke="var(--color-text-muted)" fontSize={11} axisLine={false} tickLine={false} dx={0}
                tickFormatter={(v) => `$${Number(v).toFixed(2)}`}
              />
              <YAxis yAxisId="news" orientation="left" domain={[0, maxNewsCount * 4]} hide />
              
              <Tooltip 
                content={<ChartTooltip interval={interval} />} 
                isAnimationActive={false} 
                cursor={<CustomCursor onCursorClick={handleElementClick} />}
              />
              {vis.news && (
                <Bar yAxisId="news" dataKey="dbArticleCount" fill="rgba(255,159,107,0.4)" isAnimationActive={false} maxBarSize={20} onClick={(d: any) => d && handleElementClick(d.payload || d)}>
                  {interval !== 'day' && visibleData.length <= 75 && <LabelList dataKey="dbArticleCount" position="top" fill="rgba(255,159,107,0.9)" fontSize={10} fontWeight={700} offset={2} />}
                </Bar>
              )}
              {vis.dubai && <Line yAxisId="0" type="monotone" dataKey="dubai" stroke="var(--color-primary)" strokeWidth={1.5} dot={false} connectNulls isAnimationActive={false} activeDot={{ onClick: (_e: any, p: any) => p?.payload && handleElementClick(p.payload) }} onClick={(_e: any, p: any) => p?.payload && handleElementClick(p.payload)} />}
              {vis.wti && <Line yAxisId="0" type="monotone" dataKey="wti" stroke="#34C759" strokeWidth={2} dot={false} connectNulls isAnimationActive={false} activeDot={{ onClick: (_e: any, p: any) => p?.payload && handleElementClick(p.payload) }} onClick={(_e: any, p: any) => p?.payload && handleElementClick(p.payload)} />}
              {vis.brent && <Line yAxisId="0" type="monotone" dataKey="brent" stroke="#FF9F0A" strokeWidth={1.5} dot={false} connectNulls isAnimationActive={false} activeDot={{ onClick: (_e: any, p: any) => p?.payload && handleElementClick(p.payload) }} onClick={(_e: any, p: any) => p?.payload && handleElementClick(p.payload)} />}
              <Line yAxisId="0" type="monotone" dataKey="forecastLine" stroke={upT ? 'var(--color-bull)' : 'var(--color-bear)'} strokeWidth={2} strokeDasharray="5 5" dot={false} />
              <Area yAxisId="0" type="monotone" dataKey="forecastBand" fill={`url(#${upT?'fc-bull':'fc-bear'})`} stroke="none" />
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
          <div className="chart-legend-toggles">
            <div className={`legend-toggle ${vis.dubai ? 'active' : ''}`} onClick={() => toggleVis('dubai')}>
              <span className="legend-dot" style={{ background: 'var(--color-primary)' }} /> Dubai
            </div>
            <div className={`legend-toggle ${vis.wti ? 'active' : ''}`} onClick={() => toggleVis('wti')}>
              <span className="legend-dot" style={{ background: '#34C759' }} /> WTI
            </div>
            <div className={`legend-toggle ${vis.brent ? 'active' : ''}`} onClick={() => toggleVis('brent')}>
              <span className="legend-dot" style={{ background: '#FF9F0A' }} /> Brent
            </div>
            <div className={`legend-toggle ${vis.news ? 'active' : ''}`} onClick={() => toggleVis('news')}>
              <span className="legend-dot" style={{ background: 'rgba(255,159,107,0.8)', borderRadius: '2px' }} /> 기사 건수
            </div>
          </div>
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
