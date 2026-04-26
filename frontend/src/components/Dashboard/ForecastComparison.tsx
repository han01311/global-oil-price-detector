import React, { useEffect, useState } from 'react';
import { fetchDualForecast } from '../../services/api';
import type { DualForecastResult, CrudeForecast, FundamentalCrudeForecast, FundamentalSignal } from '../../types/forecast';
import './ForecastComparison.css';

const CRUDE_LABELS: Record<string, string> = {
  dubai: 'Dubai',
  wti: 'WTI',
  brent: 'Brent',
};

const CRUDE_ORDER = ['dubai', 'wti', 'brent'];

function formatPrice(price: number | undefined): string {
  if (price === undefined || isNaN(price)) return '—';
  return `$${price.toFixed(2)}`;
}

function formatPct(current: number, forecast: number): string {
  if (!current || !forecast) return '';
  const pct = ((forecast - current) / current) * 100;
  const sign = pct >= 0 ? '+' : '';
  return `${sign}${pct.toFixed(2)}%`;
}

function getPctClass(current: number, forecast: number): string {
  if (!current || !forecast) return '';
  return forecast >= current ? 'bull' : 'bear';
}

function getTopSignal(signals?: FundamentalSignal[]): string {
  if (!signals || signals.length === 0) return '';
  const active = signals.filter(s => s.change !== null && s.weight > 0);
  if (active.length === 0) return '';
  const top = active.reduce((a, b) => (a.weight > b.weight ? a : b));
  return top.name;
}

/* ──────────────────────────────────────────────
 * Methodology Info Modal
 * ────────────────────────────────────────────── */

const METHOD_A_INFO = {
  title: '기술적 분석 모델 (Technical Analysis)',
  subtitle: 'XGBoost ML + 뉴스 감성 보정',
  description: '과거 5년간의 가격 패턴과 거시경제 지표를 머신러닝(XGBoost)으로 학습하고, 최신 뉴스의 시장 영향을 학술 근거 기반으로 보정하여 최종 전망치를 산출합니다.',
  sections: [
    {
      title: '1단계: XGBoost 베이스라인 예측',
      items: [
        '5년치 일별 유가 데이터로 학습된 Gradient Boosting 모델',
        '이동평균(5/10/20/50일), 변동성(20일), RSI, MACD 등 기술적 지표 활용',
        '유종 간 스프레드(Dubai-WTI, Brent-WTI) 반영',
        'FRED 거시경제 데이터(달러 인덱스, 금리) 연동',
        '7일/30일 독립 모델로 단기·중기 예측 분리',
      ],
    },
    {
      title: '2단계: 뉴스 감성 보정 (학술 근거 기반)',
      items: [
        '시간 감쇠 (Temporal Decay): 기사 발행일로부터 지수적으로 영향력 감소. 지정학 이슈는 반감기 5일, 일반 수급은 2.5일 적용 (arXiv 2024)',
        '의미적 중복 제거 (Semantic Deduplication): 같은 사건의 반복 보도를 자카드 유사도로 클러스터링하여 이슈 과대평가 방지 (BERT/LLM 방법론)',
        '변동성 국면 인식 (Volatility Regime): 고변동 시장에서는 뉴스 반응을 1.5배 확대, 저변동 시장에서는 0.7배 축소 (GARCH 개념, Bollerslev 1986)',
        '시장 반영도 체크 (Price Absorption): 이미 가격에 반영된 뉴스 효과를 차감. 최소 20% 모멘텀 유지 (효율적 시장 가설 변형)',
      ],
    },
    {
      title: '3단계: 유사 사례 기반 보정 (Market Memory)',
      items: [
        '20년치 주요 이벤트와 실제 가격 반응을 ChromaDB에 벡터로 저장',
        '현재 뉴스와 코사인 유사도가 높은 과거 사례 5건 검색',
        '감성 분석 40% + 유사 사례 60% 가중 결합으로 최종 보정치 산출',
      ],
    },
    {
      title: '최종 공식',
      items: [
        '최종 전망 = 현재가 × (1 + XGBoost 예측 변화율 + 뉴스 보정치)',
        '뉴스 보정치 = (감성 보정 × 0.4 + 유사사례 보정 × 0.6) × 변동성 배율 × 시장 반영도',
      ],
    },
  ],
};

const METHOD_B_INFO = {
  title: '펀더멘탈 분석 모델 (Fundamental Analysis)',
  subtitle: '수급 균형 + 계절성 + 평균 회귀',
  description: 'EIA(미국 에너지정보청)가 실제로 사용하는 Short-Term Energy Outlook 방법론을 참고하여, 실물 시장의 수급 상태를 읽고 예측합니다. 가격 차트가 아닌 실제 재고·생산·달러 데이터를 기반으로 합니다.',
  sections: [
    {
      title: '시그널 1: 재고 변화 (Inventory Signal)',
      items: [
        'EIA 주간 원유 재고 데이터 활용 — 수급 균형의 대리 지표',
        '최근 4주간 재고 변화 추세를 계산',
        '과거 5년간 "재고가 이 속도로 줄었을 때, 7일 후 유가가 평균 몇 % 변했는가" 조회',
        '재고 감소 → 수요 > 공급 → 가격 상승 압력',
      ],
    },
    {
      title: '시그널 2: 생산량 추세 (Production Signal)',
      items: [
        'EIA 주간 미국 원유 생산량 데이터 활용',
        '미국 셰일오일 생산은 유가에 민감하게 반응 (EIA STEO 방법론)',
        '최근 4주간 생산량 변화율 → 과거 유사 시기 유가 반응 조회',
        '생산 증가 → 공급 증가 → 가격 하락 압력',
      ],
    },
    {
      title: '시그널 3: 계절적 패턴 (Seasonal Factor)',
      items: [
        '수요의 계절성: 여름 드라이빙 시즌, 겨울 난방유 시즌',
        '과거 5년간 동일 월의 7일 수익률 분포를 통계적으로 분석',
        '표준편차가 작을수록(패턴 일관적) 높은 신뢰도 부여',
        '학술 근거: Seasonal Decomposition 방법론',
      ],
    },
    {
      title: '시그널 4: 평균 회귀 (Mean Reversion)',
      items: [
        '원자재 가격은 장기적으로 평균으로 회귀하는 성질 (Ornstein-Uhlenbeck process)',
        '현재 가격의 50일 이동평균 대비 이탈도 계산',
        '과거 5년간 "이 정도 이탈했을 때, 7일 후 얼마나 회귀했는가" 조회',
        '과도하게 올랐으면 하락 압력, 과도하게 내렸으면 상승 압력',
      ],
    },
    {
      title: '시그널 5: 달러 영향 (Dollar Correlation)',
      items: [
        '유가-달러 역상관 관계는 학술적으로 검증된 사실',
        '최근 7일간 달러 인덱스 변화율 확인',
        '과거 5년간 "달러가 이만큼 움직였을 때, 유가가 어떻게 반응했는가" 조회',
        '역사적 상관계수 기반 추정으로 폴백',
      ],
    },
    {
      title: '최종 합산',
      items: [
        '5개 시그널을 각각의 신뢰도(confidence)에 비례하여 가중 합산',
        '활성 시그널이 많을수록, 방향이 일치할수록 종합 신뢰도 상승',
        '극단값 ±10% 클리핑 적용',
        '불확실성 밴드: 시그널 분산 기반으로 상·하한 범위 제공',
      ],
    },
  ],
};

interface MethodInfoModalProps {
  info: typeof METHOD_A_INFO;
  onClose: () => void;
}

const MethodInfoModal: React.FC<MethodInfoModalProps> = ({ info, onClose }) => (
  <div className="fc-modal-overlay" onClick={onClose}>
    <div className="fc-modal" onClick={e => e.stopPropagation()}>
      <div className="fc-modal-header">
        <div>
          <h3 className="fc-modal-title">{info.title}</h3>
          <p className="fc-modal-subtitle">{info.subtitle}</p>
        </div>
        <button className="fc-modal-close" onClick={onClose} aria-label="Close">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="4" y1="4" x2="12" y2="12" />
            <line x1="12" y1="4" x2="4" y2="12" />
          </svg>
        </button>
      </div>

      <p className="fc-modal-desc">{info.description}</p>

      <div className="fc-modal-sections">
        {info.sections.map((section, i) => (
          <div key={i} className="fc-modal-section">
            <h4 className="fc-modal-section-title">{section.title}</h4>
            <ul className="fc-modal-list">
              {section.items.map((item, j) => (
                <li key={j}>{item}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  </div>
);

/* ──────────────────────────────────────────────
 * Unified Crude Row — combines current price + both forecasts
 * ────────────────────────────────────────────── */

interface CrudeRowProps {
  crude: string;
  methodA?: CrudeForecast;
  methodB?: FundamentalCrudeForecast;
  loading: boolean;
}

const CrudeRow: React.FC<CrudeRowProps> = ({ crude, methodA, methodB, loading }) => {
  const currentPrice = methodA?.current_price ?? methodB?.current_price;

  return (
    <div className="fc-crude-row">
      {/* Current Price Block */}
      <div className="fc-crude-current">
        <span className="fc-crude-label">{CRUDE_LABELS[crude] || crude}</span>
        {loading || currentPrice === undefined ? (
          <div className="fc-skeleton fc-skeleton-lg" />
        ) : (
          <span className="fc-current-price">{formatPrice(currentPrice)}</span>
        )}
      </div>

      {/* Forecast Columns */}
      <div className="fc-crude-forecasts">
        {/* Method A */}
        <div className="fc-forecast-cell">
          {loading || !methodA ? (
            <>
              <div className="fc-skeleton fc-skeleton-sm" />
              <div className="fc-skeleton fc-skeleton-xs" />
            </>
          ) : (
            <>
              <span className={`fc-forecast-price ${getPctClass(methodA.current_price, methodA.estimated_7d)}`}>
                {formatPrice(methodA.estimated_7d)}
              </span>
              <span className={`fc-forecast-pct ${getPctClass(methodA.current_price, methodA.estimated_7d)}`}>
                {formatPct(methodA.current_price, methodA.estimated_7d)}
              </span>
            </>
          )}
        </div>

        {/* Method B */}
        <div className="fc-forecast-cell">
          {loading || !methodB ? (
            <>
              <div className="fc-skeleton fc-skeleton-sm" />
              <div className="fc-skeleton fc-skeleton-xs" />
            </>
          ) : (
            <>
              <span className={`fc-forecast-price ${getPctClass(methodB.current_price, methodB.estimated_7d)}`}>
                {formatPrice(methodB.estimated_7d)}
              </span>
              <span className={`fc-forecast-pct ${getPctClass(methodB.current_price, methodB.estimated_7d)}`}>
                {methodB.total_change_pct >= 0 ? '+' : ''}{methodB.total_change_pct.toFixed(2)}%
              </span>
              {getTopSignal(methodB.signals) && (
                <span className="fc-signal-tag">{getTopSignal(methodB.signals)}</span>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};


/* ──────────────────────────────────────────────
 * Main Component
 * ────────────────────────────────────────────── */

export const ForecastComparison: React.FC = () => {
  const [dualData, setDualData] = useState<DualForecastResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [infoModal, setInfoModal] = useState<'A' | 'B' | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await fetchDualForecast();
        if (!cancelled) {
          setDualData(result);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '예측 데이터를 불러올 수 없습니다.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => { cancelled = true; };
  }, []);

  const methodACrudes = dualData?.method_a?.forecasts_by_crude || {};
  const methodBCrudes = dualData?.method_b?.forecasts_by_crude || {};

  return (
    <>
      <div className="forecast-comparison fade-in" id="forecast-comparison">
        {/* Header */}
        <div className="fc-header">
          <h3 className="fc-header-title">Crude Oil Price Forecast</h3>
          {dualData && (
            <span className={`fc-consensus-badge ${dualData.consensus ? 'agree' : 'disagree'}`}>
              {dualData.consensus ? '✓ 방향 일치' : '⚠ 방향 불일치'}
            </span>
          )}
        </div>

        {error && (
          <div style={{ padding: '16px', textAlign: 'center' }}>
            <p style={{ color: 'var(--color-text-muted)', fontSize: '12px' }}>{error}</p>
          </div>
        )}

        {/* Column Headers */}
        <div className="fc-column-headers">
          <div className="fc-col-current">현재가</div>
          <div className="fc-col-forecasts">
            <div className="fc-col-method">
              <span className="fc-col-method-icon">⚡</span>
              <span>기술적 분석</span>
              <button
                className="fc-info-btn"
                onClick={() => setInfoModal('A')}
                title="기술적 분석 모델 상세 정보"
                aria-label="기술적 분석 모델 정보"
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                  <circle cx="7" cy="7" r="6" />
                  <line x1="7" y1="6.5" x2="7" y2="10" />
                  <circle cx="7" cy="4.5" r="0.5" fill="currentColor" stroke="none" />
                </svg>
              </button>
            </div>
            <div className="fc-col-method">
              <span className="fc-col-method-icon">📊</span>
              <span>펀더멘탈 분석</span>
              <button
                className="fc-info-btn"
                onClick={() => setInfoModal('B')}
                title="펀더멘탈 분석 모델 상세 정보"
                aria-label="펀더멘탈 분석 모델 정보"
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                  <circle cx="7" cy="7" r="6" />
                  <line x1="7" y1="6.5" x2="7" y2="10" />
                  <circle cx="7" cy="4.5" r="0.5" fill="currentColor" stroke="none" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Crude Rows */}
        {CRUDE_ORDER.map(crude => (
          <CrudeRow
            key={crude}
            crude={crude}
            methodA={methodACrudes[crude]}
            methodB={methodBCrudes[crude]}
            loading={loading}
          />
        ))}

        {/* 7-Day Label */}
        <div className="fc-footer-note">7일 전망 기준 · 매시간 갱신</div>
      </div>

      {/* Info Modals */}
      {infoModal === 'A' && (
        <MethodInfoModal info={METHOD_A_INFO} onClose={() => setInfoModal(null)} />
      )}
      {infoModal === 'B' && (
        <MethodInfoModal info={METHOD_B_INFO} onClose={() => setInfoModal(null)} />
      )}
    </>
  );
};
