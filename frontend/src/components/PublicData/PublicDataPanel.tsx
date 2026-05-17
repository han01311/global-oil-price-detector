import React, { useState, useEffect, useMemo } from 'react';
import { Card } from '../common/Card';
import { Skeleton } from '../common/Skeleton';
import { EmptyState } from '../common/EmptyState';
import { Tooltip } from '../common/Tooltip';
import {
  fetchImportConcentration,
  fetchWorldOilTrade,
} from '../../services/api';
import type {
  ImportConcentrationData,
  WorldOilTradeData,
} from '../../services/api';
import './PublicDataPanel.css';

// ── 유종별 지역 매핑 ──
// 각 벤치마크 유가가 반영하는 산유국/지역 그룹
const CRUDE_REGION_MAP = {
  dubai: {
    label: 'Dubai',
    subtitle: '중동 벤치마크',
    color: 'var(--color-cat-geopolitics)',
    importCountries: [
      '사우디아라비아', '아랍에미레이트', '쿠웨이트', '이라크', '이란',
      '카타르', '오만', '예멘', '중립지대',
    ],
    tradeExporters: ['사우디', 'UAE', '쿠웨이트', '이라크', '기타 중동 지역'],
    tradeImporters: ['중국', '인도', '일본', '기타 아시아 지역', '싱가포르'],
    riskNote: '호르무즈 해협 통과 물량의 ~30%가 한국행',
    priceContext: '한국이 수입하는 원유의 대부분이 이 지역에서 오며, Dubai유 가격으로 거래됩니다. 중동 지정학 이슈 시 직접적인 가격 영향을 받습니다.',
    emptyImportNote: '',
  },
  brent: {
    label: 'Brent',
    subtitle: '유럽·아프리카 벤치마크',
    color: 'var(--color-primary)',
    importCountries: [
      '노르웨이', '영국', '나이지리아', '알제리', '리비아',
      '앙골라', '카메룬', '콩고', '가봉', '적도기니', '이집트',
      '튀니지', '수단', '모잠비크',
    ],
    tradeExporters: ['유럽', '북아프리카', '서아프리카', '기타 아프리카 지역', 'CIS 지역'],
    tradeImporters: ['유럽', '중국', '미국', '인도'],
    riskNote: '북해 생산량 감소 추세 → Brent 프리미엄 구조',
    priceContext: '글로벌 원유 거래의 기준 가격입니다. 유럽·아프리카 공급 차질 시 전 세계 유가에 파급됩니다.',
    emptyImportNote: '한국은 이 지역에서 직접 수입하지 않지만, Brent는 국제유가의 기준 지표로서 Dubai·WTI 가격에 영향을 미칩니다.',
  },
  wti: {
    label: 'WTI',
    subtitle: '미주 벤치마크',
    color: 'var(--color-bull)',
    importCountries: [
      '미국', '캐나다', '멕시코', '브라질', '에콰도르',
      '베네수엘라', '페루', '아르헨티나', '콜롬비아', '볼리비아',
    ],
    tradeExporters: ['캐나다', '멕시코', '미국', '중남미'],
    tradeImporters: ['미국', '유럽', '중국', '인도'],
    riskNote: '캐나다→미국 파이프라인이 세계 최대 단일 교역 루트',
    priceContext: '미국 내 원유 수급과 셰일오일 생산량에 따라 결정됩니다. 미국 원유 재고 변동이 WTI 가격의 핵심 변수입니다.',
    emptyImportNote: '',
  },
} as const;

type CrudeKey = keyof typeof CRUDE_REGION_MAP;

export const PublicDataPanel: React.FC = () => {
  const [activeCrude, setActiveCrude] = useState<CrudeKey>('dubai');
  const [hhi, setHHI] = useState<ImportConcentrationData | null>(null);
  const [trade, setTrade] = useState<WorldOilTradeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [hhiData, tradeData] = await Promise.all([
          fetchImportConcentration(),
          fetchWorldOilTrade(50),
        ]);
        if (!cancelled) {
          setHHI(hhiData);
          setTrade(tradeData);
        }
      } catch (e: any) {
        if (!cancelled) setError(e.message || '공공데이터 로드 실패');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  // ── 유종별 한국 수입 점유율 + 지역별 HHI 계산 ──
  const importStats = useMemo(() => {
    if (!hhi || 'error' in hhi || !hhi.top_countries) return null;

    const stats: Record<CrudeKey, {
      countries: typeof hhi.top_countries;
      totalPct: number;
      totalVolume: number;
      regionHHI: number;
      regionRisk: 'high' | 'medium' | 'low';
      topCountry: string | null;
      topShareInRegion: number;
    }> = {
      dubai: { countries: [], totalPct: 0, totalVolume: 0, regionHHI: 0, regionRisk: 'low', topCountry: null, topShareInRegion: 0 },
      brent: { countries: [], totalPct: 0, totalVolume: 0, regionHHI: 0, regionRisk: 'low', topCountry: null, topShareInRegion: 0 },
      wti: { countries: [], totalPct: 0, totalVolume: 0, regionHHI: 0, regionRisk: 'low', topCountry: null, topShareInRegion: 0 },
    };

    // 1차: 국가 분류 + 전체 수입 기준 점유율 합산
    for (const c of hhi.top_countries) {
      for (const [crude, cfg] of Object.entries(CRUDE_REGION_MAP)) {
        if (cfg.importCountries.includes(c.country)) {
          const key = crude as CrudeKey;
          stats[key].countries.push(c);
          stats[key].totalPct += c.share_pct;
          stats[key].totalVolume += c.volume;
        }
      }
    }

    // 2차: 지역 내 점유율을 재계산하여 HHI 산출
    for (const key of Object.keys(stats) as CrudeKey[]) {
      const s = stats[key];
      if (s.totalVolume === 0) continue;

      let hhiSum = 0;
      let maxShare = 0;
      let maxCountry = '';

      for (const c of s.countries) {
        // 지역 내 점유율 = (각 국가 물량 / 지역 총 물량) * 100
        const regionShare = (c.volume / s.totalVolume) * 100;
        hhiSum += regionShare * regionShare;
        if (regionShare > maxShare) {
          maxShare = regionShare;
          maxCountry = c.country;
        }
      }

      s.regionHHI = Math.round(hhiSum * 10) / 10;
      s.regionRisk = hhiSum >= 2500 ? 'high' : hhiSum >= 1500 ? 'medium' : 'low';
      s.topCountry = maxCountry;
      s.topShareInRegion = Math.round(maxShare * 10) / 10;
    }

    return stats;
  }, [hhi]);

  // ── 유종별 세계 교역 통계 ──
  const tradeStats = useMemo(() => {
    if (!trade || 'error' in trade) return null;

    const stats: Record<CrudeKey, { flows: typeof trade.top_flows; totalVolume: number }> = {
      dubai: { flows: [], totalVolume: 0 },
      brent: { flows: [], totalVolume: 0 },
      wti: { flows: [], totalVolume: 0 },
    };

    for (const f of trade.top_flows) {
      for (const [crude, cfg] of Object.entries(CRUDE_REGION_MAP)) {
        if (cfg.tradeExporters.some(e => f.exporter.includes(e))) {
          const key = crude as CrudeKey;
          stats[key].flows.push(f);
          stats[key].totalVolume += f.volume_mt;
        }
      }
    }

    return stats;
  }, [trade]);

  const cfg = CRUDE_REGION_MAP[activeCrude];

  const renderContent = () => {
    if (loading) {
      return (
        <div className="pdp-skeleton">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} height="24px" />)}
        </div>
      );
    }
    if (error) {
      return (
        <div className="error-fallback-partial">
          <p className="error-fallback-title">공공데이터를 불러올 수 없습니다</p>
          <p className="error-fallback-module">{error}</p>
          <button className="error-retry-button" onClick={() => window.location.reload()}>재시도</button>
        </div>
      );
    }
    if (!importStats && !tradeStats) {
      return <EmptyState icon="chart" title="공공데이터가 없습니다" description="CSV 적재 후 자동 표시됩니다." />;
    }

    const iStats = importStats?.[activeCrude];
    const tStats = tradeStats?.[activeCrude];
    const maxImportVol = iStats?.countries[0]?.volume ?? 1;
    const maxTradeVol = tStats?.flows[0]?.volume_mt ?? 1;

    // 천배럴 → 읽기 좋은 단위로 변환
    const fmtVol = (thousandBarrels: number) => {
      const manBarrels = thousandBarrels / 10; // 천배럴 → 만배럴
      if (manBarrels >= 10000) return `${(manBarrels / 10000).toFixed(1)}억`;
      return `${Math.round(manBarrels).toLocaleString()}만`;
    };

    return (
      <div className="pdp-content">
        {/* ── 유종별 요약 헤더 ── */}
        <div className="pdp-crude-summary">
          <div className="pdp-crude-badge" style={{ borderColor: cfg.color }}>
            <span className="pdp-crude-name" style={{ color: cfg.color }}>{cfg.label}</span>
            <span className="pdp-crude-subtitle">{cfg.subtitle}</span>
          </div>

          {iStats && iStats.totalPct > 0 && (
            <div className="pdp-stat-group">
              <Tooltip content={`한국 전체 원유 수입 중 ${cfg.label} 벤치마크 지역 국가들의 비중`}>
                <div className="pdp-stat">
                  <span className="pdp-stat-value" style={{ color: cfg.color }}>
                    {iStats.totalPct.toFixed(1)}%
                  </span>
                  <span className="pdp-stat-label">한국 수입 중 비중</span>
                </div>
              </Tooltip>
              <Tooltip content={`이 지역에서 한국이 연간 수입한 원유 총량 (${fmtVol(iStats.totalVolume)}배럴)`}>
                <div className="pdp-stat">
                  <span className="pdp-stat-value">{fmtVol(iStats.totalVolume)}<small className="pdp-stat-unit">배럴</small></span>
                  <span className="pdp-stat-label">총 수입량</span>
                </div>
              </Tooltip>
              <div className="pdp-stat">
                <span className="pdp-stat-value">{iStats.countries.length}</span>
                <span className="pdp-stat-label">수입 대상국</span>
              </div>
            </div>
          )}
        </div>

        {/* ── 유가 연관성 설명 ── */}
        <div className="pdp-price-context">
          {cfg.priceContext}
        </div>

        {/* ── 참고 노트 ── */}
        <div className="pdp-risk-note">
          <svg width="14" height="14" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="10" cy="10" r="8.5" />
            <line x1="10" y1="8" x2="10" y2="12" />
            <circle cx="10" cy="6" r="0.5" fill="currentColor" />
          </svg>
          {cfg.riskNote}
        </div>

        {/* ── 2-Column: 한국 수입처 + 세계 교역 흐름 ── */}
        <div className="pdp-two-col">
          {/* 한국 수입처 */}
          <div className="pdp-col">
            <div className="pdp-col-title">
              <span className="pdp-col-icon">🇰🇷</span>
              한국이 수입하는 국가 ({hhi && !('error' in hhi) ? `${hhi.year}년` : ''})
            </div>
            <div className="pdp-col-subtitle">
              국가별 수입 비중과 물량
            </div>
            {iStats && iStats.countries.length > 0 ? (
              iStats.countries.slice(0, 6).map((c, i) => (
                <div key={c.country} className="pdp-bar-row-dual slide-up" style={{ animationDelay: `${i * 0.04}s` }}>
                  <span className="pdp-bar-label">{c.country}</span>
                  <div className="pdp-bar-track">
                    <div
                      className="pdp-bar-fill"
                      style={{
                        width: `${(c.volume / maxImportVol) * 100}%`,
                        backgroundColor: cfg.color,
                      }}
                    />
                  </div>
                  <span className="pdp-bar-pct">{c.share_pct}%</span>
                  <span className="pdp-bar-vol">{fmtVol(c.volume)}<small>배럴</small></span>
                </div>
              ))
            ) : (
              <div className="pdp-empty-context">
                {cfg.emptyImportNote || '해당 벤치마크 지역에서 직접 수입하지 않습니다.'}
              </div>
            )}
          </div>

          {/* 이 지역 원유의 주요 수출처 */}
          <div className="pdp-col">
            <div className="pdp-col-title">
              <span className="pdp-col-icon">🌍</span>
              이 지역의 원유는 어디로? ({trade && !('error' in trade) ? `${trade.data_year}년` : ''})
            </div>
            <div className="pdp-col-subtitle">
              같은 원유를 사는 다른 나라들 — 수요 경쟁이 가격에 영향
            </div>
            {tStats && tStats.flows.length > 0 ? (
              tStats.flows.slice(0, 6).map((f, i) => (
                <div key={`${f.exporter}-${f.importer}`} className="pdp-flow-row slide-up" style={{ animationDelay: `${i * 0.04}s` }}>
                  <span className="pdp-flow-from">{f.exporter}</span>
                  <span className="pdp-flow-arrow">→</span>
                  <span className="pdp-flow-to">{f.importer}</span>
                  <div className="pdp-bar-track" style={{ flex: 1 }}>
                    <div
                      className="pdp-bar-fill"
                      style={{
                        width: `${(f.volume_mt / maxTradeVol) * 100}%`,
                        backgroundColor: cfg.color,
                        opacity: 0.6,
                      }}
                    />
                  </div>
                  <span className="pdp-bar-value">{f.volume_mt}<small>백만톤</small></span>
                </div>
              ))
            ) : (
              <div className="pdp-empty-note">교역 데이터 없음</div>
            )}
          </div>
        </div>

        <div className="pdp-source">
          출처: 한국석유공사(KNOC) 공공데이터포털 · 참고 자료
        </div>
      </div>
    );
  };

  const riskColor = (level: string) =>
    level === 'high' ? 'var(--color-bear)'
      : level === 'medium' ? 'var(--color-warning)'
      : 'var(--color-bull)';

  const riskLabel = (level: string) =>
    level === 'high' ? '고집중' : level === 'medium' ? '중집중' : '저집중';

  return (
    <Card title="Supply Structure · 유종별 공급 구조" className="pdp-card">
      {/* 유종 3탭 */}
      <div className="pdp-tabs">
        {(Object.keys(CRUDE_REGION_MAP) as CrudeKey[]).map((key) => {
          const c = CRUDE_REGION_MAP[key];
          const pct = importStats?.[key]?.totalPct;
          return (
            <button
              key={key}
              className={`pdp-tab ${activeCrude === key ? 'active' : ''}`}
              onClick={() => setActiveCrude(key)}
              style={activeCrude === key ? { borderBottomColor: c.color } : undefined}
            >
              <span className="pdp-tab-label" style={activeCrude === key ? { color: c.color } : undefined}>
                {c.label}
              </span>
              {pct !== undefined && pct > 0 && (
                <span className="pdp-tab-pct">{pct.toFixed(0)}%</span>
              )}
            </button>
          );
        })}
      </div>

      {/* 유종별 탭 콘텐츠 */}
      {renderContent()}

      {/* ── 하단: 한국 전체 수입 집중도 (HHI) ── */}
      {!loading && !error && hhi && !('error' in hhi) && (
        <div className="pdp-hhi-section">
          <div className="pdp-hhi-header-row">
            <span className="pdp-hhi-section-label">🇰🇷 한국 전체 원유 수입 집중도</span>
            <span className="pdp-hhi-year">{hhi.year}년 · {hhi.country_count}개국에서 수입</span>
          </div>

          <div className="pdp-hhi-main">
            <div className="pdp-hhi-value-group">
              <span className="pdp-hhi-big-value" style={{ color: riskColor(hhi.risk_level) }}>
                {hhi.hhi.toLocaleString()}
              </span>
              <span className="pdp-hhi-big-risk" style={{ color: riskColor(hhi.risk_level) }}>
                {riskLabel(hhi.risk_level)}
              </span>
            </div>
            <div className="pdp-hhi-gauge-track">
              <div className="pdp-hhi-gauge-zone low" />
              <div className="pdp-hhi-gauge-zone medium" />
              <div className="pdp-hhi-gauge-zone high" />
              <div
                className="pdp-hhi-gauge-needle"
                style={{ left: `${Math.min((hhi.hhi / 5000) * 100, 100)}%` }}
              />
            </div>
            <div className="pdp-hhi-gauge-labels">
              <span>0</span>
              <span>저집중</span>
              <span>1500</span>
              <span>중집중</span>
              <span>2500</span>
              <span>고집중</span>
              <span>5000</span>
            </div>
          </div>

          <div className="pdp-hhi-desc">
            <p className="pdp-hhi-desc-title">HHI(수입 집중도 지수)란?</p>
            <p>한국이 원유를 수입하는 각 국가의 점유율(백분율)을 제곱하여 합산한 값입니다.
              한 국가에서 100% 수입하면 10,000, 완전히 분산되면 0에 가까워집니다.</p>
            <p>현재 한국의 HHI <strong>{hhi.hhi.toLocaleString()}</strong>는{' '}
              {hhi.risk_level === 'high'
                ? '소수 국가에 과도하게 의존하고 있어, 지정학 리스크에 취약함을 의미합니다.'
                : hhi.risk_level === 'medium'
                ? '중간 수준의 집중도로, 특정 국가(특히 사우디아라비아 32%)에 다소 의존적이나 심각한 수준은 아닙니다.'
                : '수입원이 잘 분산되어 있어, 특정 국가 공급 차질에 대한 비켓이 마련되어 있습니다.'}
            </p>
          </div>
        </div>
      )}
    </Card>
  );
};
