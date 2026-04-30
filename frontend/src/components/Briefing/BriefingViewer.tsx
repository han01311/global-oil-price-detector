import React, { useCallback, useState } from 'react';
import { useBriefing } from '../../hooks/useBriefing';
import { Skeleton } from '../common/Skeleton';
import { Badge } from '../common/Badge';
import { EmptyState } from '../common/EmptyState';
import './BriefingViewer.css';
import type { Briefing, BriefingKeyFactor, RiskScenario, CrudeDailyAssessment } from '../../types/forecast';

const BriefingSection: React.FC<{ title: React.ReactNode; icon: string; children: React.ReactNode }> = ({ title, icon, children }) => (
  <div className="briefing-section">
    <h4 className="briefing-section-title">
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span>{icon}</span>
        <span>{title}</span>
      </div>
    </h4>
    {children}
  </div>
);

const KeyFactors: React.FC<{ factors: BriefingKeyFactor[] }> = ({ factors }) => (
  <ul className="key-factors-list">
    {factors.map((factor, index) => (
      <li key={index} className="key-factor-item">
        <div className="key-factor-header">
          <Badge category={factor.category as any} />
          <span className={`key-factor-score ${factor.impact}`}>
            {factor.score > 0 ? '+' : ''}{factor.score}
          </span>
        </div>
        <p className="key-factor-description">{factor.description}</p>
      </li>
    ))}
  </ul>
);

const RiskScenarios: React.FC<{ scenarios: RiskScenario[] }> = ({ scenarios }) => (
  <ul className="risk-scenarios-list">
    {scenarios.map((scenario, index) => (
      <li key={index} className="risk-scenario-item">
        <span className={`risk-probability risk-probability-${scenario.probability}`}>{scenario.probability}</span>
        <span>{scenario.scenario}</span>
        <span className="risk-impact">{scenario.price_impact}</span>
      </li>
    ))}
  </ul>
);

const CRUDE_LABELS: Record<string, string> = {
  dubai: 'Dubai',
  brent: 'Brent',
  wti: 'WTI',
};

const DIRECTION_LABELS: Record<string, string> = {
  bullish: '상승',
  bearish: '하락',
  neutral: '보합',
};

const CrudeDailyAssessments: React.FC<{ assessments: CrudeDailyAssessment[] }> = ({ assessments }) => (
  <div className="crude-assessments-grid">
    {assessments.map((item) => (
      <div key={item.crude_type} className={`crude-assessment-card ${item.direction}`}>
        <div className="crude-assessment-header">
          <span className="crude-assessment-label">{CRUDE_LABELS[item.crude_type] || item.crude_type}</span>
          <span className={`crude-assessment-change ${item.direction}`}>
            {item.direction === 'bullish' ? '▲' : item.direction === 'bearish' ? '▼' : '—'}
            {' '}{DIRECTION_LABELS[item.direction] || item.direction}
            {' '}{item.change_pct > 0 ? '+' : ''}{item.change_pct.toFixed(2)}%
          </span>
        </div>
        <p className="crude-assessment-driver">{item.key_driver}</p>
      </div>
    ))}
  </div>
);

const BriefingContent: React.FC<{ briefing: Briefing }> = ({ briefing }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="briefing-content-wrapper">
      <div className={`briefing-viewer ${isExpanded ? 'expanded' : 'collapsed'}`}>
        <BriefingSection title="핵심 요약" icon="📋">
          <div className="briefing-summary">
            <p>{briefing.summary}</p>
            <p style={{ marginTop: '8px', color: 'var(--color-text-secondary)', fontStyle: 'italic' }}>
              {briefing.price_outlook}
            </p>
          </div>
        </BriefingSection>

        {briefing.crude_assessments && briefing.crude_assessments.length > 0 && (
          <BriefingSection 
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                유종별 당일 시세
                <span style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 'normal' }}>
                  (전일 종가 대비)
                </span>
              </div>
            } 
            icon="🛢️"
          >
            <CrudeDailyAssessments assessments={briefing.crude_assessments} />
          </BriefingSection>
        )}

        {briefing.key_factors.length > 0 && (
          <BriefingSection title="주요 요인" icon="📊">
            <KeyFactors factors={briefing.key_factors} />
          </BriefingSection>
        )}

        {briefing.risk_scenarios.length > 0 && (
          <BriefingSection title="리스크 시나리오" icon="⚠">
            <RiskScenarios scenarios={briefing.risk_scenarios} />
          </BriefingSection>
        )}
      </div>
      
      {!isExpanded && <div className="briefing-fade-overlay" />}
      
      <div className={`briefing-toggle-container ${isExpanded ? 'expanded' : ''}`}>
        <button 
          className="briefing-toggle-btn" 
          onClick={() => setIsExpanded(!isExpanded)}
        >
          {isExpanded ? '▲ 접기' : '▼ 더보기'}
        </button>
      </div>
    </div>
  );
};

export const BriefingViewer: React.FC = () => {
  const { currentBriefing, loading, error, goToPrevious, goToNext, hasPrevious, hasNext, refetch } = useBriefing();

  const handleRetry = useCallback(() => {
    refetch?.();
  }, [refetch]);

  if (loading) {
    return (
      <>
        <Skeleton height="20px" width="100%" style={{ marginBottom: '16px' }} />
        <Skeleton height="60px" width="100%" style={{ marginBottom: '24px' }} />
        <Skeleton height="120px" width="100%" />
      </>
    );
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
        <p className="error-fallback-title">브리핑을 불러올 수 없습니다</p>
        <p className="error-fallback-module">{error.message}</p>
        <button className="error-retry-button" onClick={handleRetry}>
          재시도
        </button>
      </div>
    );
  }

  if (!currentBriefing) {
    return (
      <EmptyState
        icon="briefing"
        title="생성된 브리핑이 없습니다"
        description="AI 브리핑이 아직 생성되지 않았거나 데이터가 부족합니다."
      />
    );
  }

  return (
    <>
      <div className="briefing-header">
        <span className="briefing-date">
          {new Date(currentBriefing.date).toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' })} Briefing
        </span>
        <div className="briefing-nav">
          <button onClick={goToPrevious} disabled={!hasPrevious}>&lt; 이전</button>
          <button onClick={goToNext} disabled={!hasNext}>다음 &gt;</button>
        </div>
      </div>
      <BriefingContent briefing={currentBriefing} />
    </>
  );
};
