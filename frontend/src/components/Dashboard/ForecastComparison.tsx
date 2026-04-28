import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom';
import { Card } from '../common/Card';
import { Skeleton } from '../common/Skeleton';
import { EmptyState } from '../common/EmptyState';
import { fetchDualForecast, fetchPriceHistory } from '../../services/api';
import type { DualForecastResult, FundamentalSignal } from '../../types/forecast';
import type { OilPrice } from '../../types/price';
import './ForecastComparison.css';

const CRUDE_LABELS: Record<string, string> = { dubai: 'Dubai', wti: 'WTI', brent: 'Brent' };
const CRUDE_ORDER = ['dubai', 'wti', 'brent'];

function formatPrice(p: number | undefined): string {
  return p === undefined || isNaN(p) ? '—' : `$${p.toFixed(2)}`;
}

function formatChange(from: number, to: number) {
  const diff = to - from;
  const pct = (diff / from) * 100;
  return {
    pct: `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`,
    diff: `${diff >= 0 ? '+' : ''}$${Math.abs(diff).toFixed(2)}`,
    isUp: diff >= 0,
  };
}

function getTopSignal(signals?: FundamentalSignal[]): string {
  if (!signals?.length) return '';
  const active = signals.filter(s => s.change !== null && s.weight > 0);
  if (!active.length) return '';
  return active.reduce((a, b) => (a.weight > b.weight ? a : b)).name;
}

function fmtDateShort(d: string) { const dt = new Date(d); return `${dt.getMonth() + 1}/${dt.getDate()}`; }
function fmtTarget(d: string) { const dt = new Date(d); dt.setDate(dt.getDate() + 7); return `${dt.getMonth() + 1}/${dt.getDate()}`; }

/* ──────────────────────────────────────────────
 * Model info data (landing-page style with steps)
 * ────────────────────────────────────────────── */

interface StepData {
  icon: string;
  step: number;
  label: string;
  summary: string;
  details: string[];
}

interface MethodData {
  title: string;
  titleEn: string;
  subtitle: string;
  description: string;
  diagramType: 'pipeline' | 'ensemble';
  steps: StepData[];
}

const METHOD_A: MethodData = {
  title: '기술적 분석 모델',
  titleEn: 'Technical Analysis',
  subtitle: 'XGBoost Gradient Boosting + News Sentiment Adjustment',
  description: '과거 5년간 멀티팩터 시계열 데이터를 XGBoost로 학습하고, 실시간 뉴스 감성 분석을 5단계 파이프라인으로 보정하여 최종 7일 전망치를 산출합니다.',
  diagramType: 'pipeline',
  steps: [
    {
      icon: '🧠', step: 1, label: 'XGBoost 베이스라인',
      summary: '18개 기술적 지표 + 거시경제 데이터로 7일 후 가격을 예측합니다.',
      details: [
        '피처: SMA(5/10/20/50), EMA(12/26), Bollinger, RSI, MACD, Stochastic 등 18개 지표',
        '스프레드: Dubai-WTI, Brent-WTI 스프레드 및 Z-score',
        '거시: FRED API — DXY 달러인덱스, 금리, 장단기금리차',
        '유종별 독립 모델 6개 학습 (Dubai/WTI/Brent × 7D/30D)',
      ],
    },
    {
      icon: '📰', step: 2, label: '뉴스 감성 보정',
      summary: '학술 논문 기반 5단계 필터로 뉴스의 실질적 영향력만 추출합니다.',
      details: [
        '시간 감쇠: 거래일(Trading Day) 기준 지수 감쇠 (휴장일 제외)',
        '시장 공백 인식: 주말/휴장 기간 기사 누적 합산 및 자동 상쇄',
        '중복 제거: Jaccard 클러스터링 기반 의미적 중복 1건으로 통합',
        '변동성 국면: 고변동 시장 시 뉴스 민감도(×1.5배) 확대',
        '시장 반영도: 실제 가격에 이미 선반영된 뉴스 효과 차감',
      ],
    },
    {
      icon: '🗂️', step: 3, label: '유사 사례 보정',
      summary: '20년치 유가 이벤트 DB에서 유사 사례를 찾아 보정합니다.',
      details: [
        'ChromaDB에 2003~2024년 주요 이벤트 약 2,000건 임베딩',
        '코사인 유사도 Top-5 과거 사례 검색 (임계값 ≥ 0.65)',
        '감성 40% + 유사사례 60% 가중 결합',
      ],
    },
    {
      icon: '🎯', step: 4, label: '최종 전망',
      summary: '베이스라인 + 뉴스 보정치를 합산하여 최종 가격을 산출합니다.',
      details: [
        'P = P_current × (1 + ΔBaseline + ΔNews)',
        'ΔNews = (Sentiment×0.4 + Analog×0.6) × VolMult × (1-Absorption)',
        '신뢰 밴드: RMSE 기반 ±1σ 구간',
      ],
    },
  ],
};

const METHOD_B: MethodData = {
  title: '펀더멘탈 분석 모델',
  titleEn: 'Fundamental Analysis',
  subtitle: 'EIA STEO Methodology + Multi-Signal Ensemble',
  description: 'EIA 방법론을 재현하여 실물 수급 데이터로 유가를 전망합니다. 5개 독립 시그널을 신뢰도 기반 가중 합산합니다.',
  diagramType: 'ensemble',
  steps: [
    {
      icon: '🛢️', step: 1, label: '재고 변화',
      summary: 'EIA 주간 원유 재고 변동으로 수급 균형을 파악합니다.',
      details: [
        '데이터: EIA Weekly Petroleum Status Report',
        '4주 누적 재고 변화량 → 조건부 수익률 조회',
        '재고 감소 = 상승 압력 / 재고 증가 = 하락 압력',
      ],
    },
    {
      icon: '⛏️', step: 2, label: '생산량',
      summary: '미국 원유 생산량 움직임으로 공급 측 변화를 추적합니다.',
      details: [
        '데이터: EIA Weekly U.S. Field Production',
        '최근 4주 vs 직전 4주 평균 생산량 변화율',
        '셰일오일 생산은 2~4개월 시차로 유가에 반응',
      ],
    },
    {
      icon: '🌡️', step: 3, label: '계절성',
      summary: '드라이빙/난방유 시즌 등 계절적 수요 패턴을 반영합니다.',
      details: [
        '5~8월 가솔린 수요 ↑ / 11~2월 난방유 수요 ↑',
        '과거 5년 동일 월 7일 수익률 분포 통계',
        '패턴 일관성 높을수록 높은 가중치',
      ],
    },
    {
      icon: '⚖️', step: 4, label: '평균 회귀',
      summary: '50일 이동평균 대비 이탈도로 회귀 압력을 측정합니다.',
      details: [
        'Ornstein-Uhlenbeck process 기반 평균 회귀 이론',
        'Z > +2σ → 하락 회귀 / Z < -2σ → 상승 회귀',
        '극단적 이탈일수록 역사적 일관성 ↑',
      ],
    },
    {
      icon: '💵', step: 5, label: '달러 상관',
      summary: 'USD 달러 인덱스와의 역상관 관계를 반영합니다.',
      details: [
        '유가-달러 역상관 r ≈ -0.4~-0.6',
        'FRED DX-Y.NYB 최근 7일 변화율 기반',
        '폴백: 역사적 β=-0.5 선형 추정',
      ],
    },
  ],
};

/* ──────────────────────────────────────────────
 * Landing-page style Modal (via Portal)
 * ────────────────────────────────────────────── */

const MethodInfoModal: React.FC<{ info: MethodData; onClose: () => void }> = ({ info, onClose }) => {
  React.useEffect(() => {
    document.body.style.overflow = 'hidden';
    const handleEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handleEsc);
    return () => {
      document.body.style.overflow = '';
      document.removeEventListener('keydown', handleEsc);
    };
  }, [onClose]);

  return ReactDOM.createPortal(
    <div className="fc-modal-overlay" onClick={onClose}>
      <div className="fc-modal" onClick={e => e.stopPropagation()}>
        {/* Hero */}
        <div className="fc-modal-hero">
          <button className="fc-modal-close" onClick={onClose} aria-label="Close">✕</button>
          <p className="fc-modal-title-en">{info.titleEn}</p>
          <h3 className="fc-modal-title">{info.title}</h3>
          <p className="fc-modal-subtitle">{info.subtitle}</p>
        </div>

        {/* Description */}
        <p className="fc-modal-desc">{info.description}</p>

        {/* Flow Diagram */}
        {info.diagramType === 'pipeline' && (
          <div className="fc-diagram">
            <div className="fc-diagram-title">Processing Pipeline</div>
            <div className="fc-pipeline">
              <div className="fc-pipe-node">
                <span className="fc-pipe-icon">📊</span>
                <span className="fc-pipe-text">가격 데이터</span>
                <span className="fc-pipe-sub">5년 시계열</span>
              </div>
              <div className="fc-pipe-arrow">→</div>
              <div className="fc-pipe-node">
                <span className="fc-pipe-icon">🧠</span>
                <span className="fc-pipe-text">XGBoost</span>
                <span className="fc-pipe-sub">18개 피처</span>
              </div>
              <div className="fc-pipe-arrow">→</div>
              <div className="fc-pipe-node">
                <span className="fc-pipe-icon">📰</span>
                <span className="fc-pipe-text">뉴스 보정</span>
                <span className="fc-pipe-sub">5단계 필터</span>
              </div>
              <div className="fc-pipe-arrow">→</div>
              <div className="fc-pipe-node">
                <span className="fc-pipe-icon">🗂️</span>
                <span className="fc-pipe-text">유사사례</span>
                <span className="fc-pipe-sub">ChromaDB</span>
              </div>
              <div className="fc-pipe-arrow">→</div>
              <div className="fc-pipe-node fc-pipe-result">
                <span className="fc-pipe-icon">🎯</span>
                <span className="fc-pipe-text">전망가</span>
                <span className="fc-pipe-sub">7D Forecast</span>
              </div>
            </div>
            <div className="fc-formula-box">
              <span className="fc-formula-label">Final Formula</span>
              <code className="fc-formula">P<sub>forecast</sub> = P<sub>current</sub> × (1 + Δ<sub>XGBoost</sub> + Δ<sub>News</sub>)</code>
            </div>
          </div>
        )}

        {info.diagramType === 'ensemble' && (
          <div className="fc-diagram">
            <div className="fc-diagram-title">Signal Ensemble</div>
            <div className="fc-ensemble">
              <div className="fc-ens-signals">
                <div className="fc-ens-signal">
                  <span className="fc-ens-icon">🛢️</span>
                  <span className="fc-ens-name">재고</span>
                </div>
                <div className="fc-ens-signal">
                  <span className="fc-ens-icon">⛏️</span>
                  <span className="fc-ens-name">생산</span>
                </div>
                <div className="fc-ens-signal">
                  <span className="fc-ens-icon">🌡️</span>
                  <span className="fc-ens-name">계절</span>
                </div>
                <div className="fc-ens-signal">
                  <span className="fc-ens-icon">⚖️</span>
                  <span className="fc-ens-name">회귀</span>
                </div>
                <div className="fc-ens-signal">
                  <span className="fc-ens-icon">💵</span>
                  <span className="fc-ens-name">달러</span>
                </div>
              </div>
              <div className="fc-ens-merge">
                <div className="fc-ens-merge-lines"></div>
                <div className="fc-ens-merge-label">∑ Weighted Average</div>
              </div>
              <div className="fc-ens-result">
                <span className="fc-pipe-icon">🎯</span>
                <span className="fc-pipe-text">전망가</span>
                <span className="fc-pipe-sub">7D Forecast</span>
              </div>
            </div>
            <div className="fc-formula-box">
              <span className="fc-formula-label">Ensemble Formula</span>
              <code className="fc-formula">Δ<sub>price</sub> = Σ(signal<sub>i</sub> × weight<sub>i</sub>) / Σ(weight<sub>i</sub>), clip ±10%</code>
            </div>
          </div>
        )}

        {/* Step cards */}
        <div className="fc-modal-steps">
          {info.steps.map((step, i) => (
            <div key={i} className="fc-step-card">
              <div className="fc-step-head">
                <span className="fc-step-icon">{step.icon}</span>
                <div className="fc-step-meta">
                  <span className="fc-step-num">STEP {step.step}</span>
                  <span className="fc-step-label">{step.label}</span>
                </div>
              </div>
              <p className="fc-step-summary">{step.summary}</p>
              <ul className="fc-step-details">
                {step.details.map((d, j) => <li key={j}>{d}</li>)}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>,
    document.body
  );
};

/* ──────────────────────────────────────────────
 * Main Component
 * ────────────────────────────────────────────── */

export const ForecastComparison: React.FC = () => {
  const [dualData, setDualData] = useState<DualForecastResult | null>(null);
  const [prevPrices, setPrevPrices] = useState<OilPrice | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [infoModal, setInfoModal] = useState<'A' | 'B' | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const endDate = new Date().toISOString().split('T')[0];
        const startDate = new Date(Date.now() - 14 * 86400000).toISOString().split('T')[0];
        const [result, historyData] = await Promise.all([
          fetchDualForecast(),
          fetchPriceHistory(startDate, endDate),
        ]);
        if (!cancelled) {
          setDualData(result);
          const prices = historyData.prices;
          if (prices.length >= 2) setPrevPrices(prices[prices.length - 2]);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : '예측 데이터를 불러올 수 없습니다.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  const methodACrudes = dualData?.method_a?.forecasts_by_crude || {};
  const methodBCrudes = dualData?.method_b?.forecasts_by_crude || {};
  const generatedAt = dualData?.generated_at || '';
  const baseDateLabel = generatedAt ? fmtDateShort(generatedAt) : '';
  const targetDateLabel = generatedAt ? fmtTarget(generatedAt) : '';

  if (error) {
    return (
      <Card title="Crude Oil Price Forecast">
        <div className="error-fallback-partial">
          <div className="error-fallback-icon">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="10" cy="10" r="8.5" />
              <line x1="7" y1="7" x2="13" y2="13" />
              <line x1="13" y1="7" x2="7" y2="13" />
            </svg>
          </div>
          <p className="error-fallback-title">예측 데이터를 불러올 수 없습니다</p>
          <p className="error-fallback-module">{error}</p>
        </div>
      </Card>
    );
  }

  if (!loading && !dualData) {
    return (
      <Card title="Crude Oil Price Forecast">
        <EmptyState icon="chart" title="전망 데이터가 없습니다" description="예측 모델이 아직 실행되지 않았습니다." />
      </Card>
    );
  }

  return (
    <>
      <Card title="Crude Oil Price Forecast">
        <div className="fc-sub-header">
          <span className="fc-date-context">
            {baseDateLabel ? `${baseDateLabel} 현재가 기준 → ${targetDateLabel} 전망 (7D)` : '데이터 로딩 중…'}
          </span>
          <div className="fc-sub-right">
            {dualData && (
              <span
                className={`fc-consensus ${dualData.consensus ? 'agree' : 'disagree'}`}
                data-tooltip="기술적 모델과 펀더멘탈 모델의 WTI 유가 예측 방향(상승/하락) 일치 여부입니다."
              >
                {dualData.consensus ? '✓ 방향 일치' : '⚠ 불일치'}
              </span>
            )}
          </div>
        </div>

        <div className="fc-table">
          <div className="fc-row fc-row-header">
            <div className="fc-cell fc-cell-name"></div>
            <div className="fc-cell fc-cell-price">현재가</div>
            <div className="fc-cell fc-cell-change">전일비</div>
            <div className="fc-cell fc-cell-forecast">
              <div className="fc-header-group">
                <span>기술적 7D</span>
                <button className="fc-info-icon-btn" onClick={() => setInfoModal('A')} title="방법론 상세 보기" aria-label="방법론 상세 보기">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                </button>
              </div>
            </div>
            <div className="fc-cell fc-cell-change">변동</div>
            <div className="fc-cell fc-cell-forecast">
              <div className="fc-header-group">
                <span>펀더멘탈 7D</span>
                <button className="fc-info-icon-btn" onClick={() => setInfoModal('B')} title="방법론 상세 보기" aria-label="방법론 상세 보기">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                </button>
              </div>
            </div>
            <div className="fc-cell fc-cell-change">변동</div>
          </div>

          {CRUDE_ORDER.map(crude => {
            const mA = methodACrudes[crude];
            const mB = methodBCrudes[crude];
            const currentPrice = mA?.current_price ?? mB?.current_price;
            const chgA = mA && currentPrice ? formatChange(currentPrice, mA.estimated_7d) : null;
            const chgB = mB && currentPrice ? formatChange(currentPrice, mB.estimated_7d) : null;
            const signal = getTopSignal(mB?.signals);
            const prevPrice = prevPrices ? (prevPrices as any)[crude] as number | null : null;
            const dayChg = currentPrice && prevPrice ? formatChange(prevPrice, currentPrice) : null;

            return (
              <div key={crude} className="fc-row">
                <div className="fc-cell fc-cell-name">{CRUDE_LABELS[crude]}</div>

                <div className="fc-cell fc-cell-price">
                  {loading || currentPrice === undefined
                    ? <Skeleton height="20px" width="70px" />
                    : <span className={`fc-val-current ${dayChg ? (dayChg.isUp ? 'bull' : 'bear') : ''}`}>{formatPrice(currentPrice)}</span>
                  }
                </div>

                <div className="fc-cell fc-cell-change">
                  {loading || !dayChg
                    ? <Skeleton height="14px" width="50px" />
                    : <span className={`fc-val-change ${dayChg.isUp ? 'bull' : 'bear'}`}>{dayChg.pct}<span className="fc-val-diff">{dayChg.diff}</span></span>
                  }
                </div>

                <div className="fc-cell fc-cell-forecast">
                  {loading || !mA
                    ? <Skeleton height="20px" width="70px" />
                    : <span className={`fc-val-forecast ${chgA?.isUp ? 'bull' : 'bear'}`}>{formatPrice(mA.estimated_7d)}</span>
                  }
                </div>

                <div className="fc-cell fc-cell-change">
                  {loading || !chgA
                    ? <Skeleton height="14px" width="50px" />
                    : <span className={`fc-val-change ${chgA.isUp ? 'bull' : 'bear'}`}>{chgA.pct}<span className="fc-val-diff">{chgA.diff}</span></span>
                  }
                </div>

                <div className="fc-cell fc-cell-forecast">
                  {loading || !mB
                    ? <Skeleton height="20px" width="70px" />
                    : <span className={`fc-val-forecast ${chgB?.isUp ? 'bull' : 'bear'}`}>{formatPrice(mB.estimated_7d)}</span>
                  }
                </div>

                <div className="fc-cell fc-cell-change">
                  {loading || !chgB
                    ? <Skeleton height="14px" width="50px" />
                    : <span className={`fc-val-change ${chgB?.isUp ? 'bull' : 'bear'}`}>{chgB?.pct}<span className="fc-val-diff">{chgB?.diff}</span>{signal && <span className="fc-signal">{signal}</span>}</span>
                  }
                </div>
              </div>
            );
          })}
        </div>

        {generatedAt && (
          <div className="fc-footer">
            매시간 갱신 · {new Date(generatedAt).toLocaleString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
          </div>
        )}
      </Card>

      {infoModal === 'A' && <MethodInfoModal info={METHOD_A} onClose={() => setInfoModal(null)} />}
      {infoModal === 'B' && <MethodInfoModal info={METHOD_B} onClose={() => setInfoModal(null)} />}
    </>
  );
};
