import React from 'react';
import { useBriefing } from '../../hooks/useBriefing';
import { Skeleton } from '../common/Skeleton';
import { Badge } from '../common/Badge';
import './BriefingViewer.css';
import type { Briefing, BriefingKeyFactor, RiskScenario, SimilarCase } from '../../types/forecast';

const BriefingSection: React.FC<{ title: string; icon: string; children: React.ReactNode }> = ({ title, icon, children }) => (
  <div className="briefing-section">
    <h4 className="briefing-section-title">
      <span>{icon}</span>
      <span>{title}</span>
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

const SimilarCases: React.FC<{ cases: SimilarCase[] }> = ({ cases }) => (
  <ul className="similar-cases-list">
    {cases.map((c, index) => {
      const isBull = c.actual_impact.includes('+');
      const isBear = c.actual_impact.includes('-');
      const impactClass = isBull ? 'bull' : isBear ? 'bear' : 'neutral';
      return (
        <li key={index} className="similar-case-item">
          <span>·</span>
          <span>{c.event} ({new Date(c.date).toLocaleDateString()})</span>
          <span className={`similar-case-impact ${impactClass}`}>{c.actual_impact}</span>
        </li>
      );
    })}
  </ul>
);

const BriefingContent: React.FC<{ briefing: Briefing }> = ({ briefing }) => (
  <div className="briefing-viewer">
    <BriefingSection title="핵심 요약" icon="📋">
      <div className="briefing-summary">
        <p>{briefing.summary}</p>
        <p style={{ marginTop: '8px', color: 'var(--color-text-secondary)', fontStyle: 'italic' }}>
          {briefing.price_outlook}
        </p>
      </div>
    </BriefingSection>

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

    {briefing.similar_cases.length > 0 && (
      <BriefingSection title="과거 유사 사례" icon="📜">
        <SimilarCases cases={briefing.similar_cases} />
      </BriefingSection>
    )}
  </div>
);

export const BriefingViewer: React.FC = () => {
  const { currentBriefing, loading, error, goToPrevious, goToNext, hasPrevious, hasNext } = useBriefing();

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
    return <p style={{ color: 'var(--color-error)' }}>Error loading briefing: {error.message}</p>;
  }

  if (!currentBriefing) {
    return <p>No briefing available.</p>;
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
