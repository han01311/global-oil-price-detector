import React from 'react';
import './Badge.css';

type Category = 'all' | 'geopolitics' | 'supply' | 'demand' | 'macro' | 'climate' | 'speculation' | 'other' | 'default';

interface BadgeProps {
  category: Category | string;
  children?: React.ReactNode;
  className?: string;
}

const categoryDisplay: Record<string, string> = {
  all: '전체',
  geopolitics: '지정학',
  supply: '공급',
  demand: '수요',
  macro: '거시경제',
  climate: '기후/ESG',
  speculation: '투기/심리',
  other: '기타',
  default: '기타'
};

export const Badge: React.FC<BadgeProps> = ({ category, children, className }) => {
  let normalizedCategory = (category || 'default').toString().toLowerCase();
  
  // Reverse mapping for Korean inputs from LLM
  if (normalizedCategory.includes('지정학')) normalizedCategory = 'geopolitics';
  else if (normalizedCategory.includes('공급')) normalizedCategory = 'supply';
  else if (normalizedCategory.includes('수요')) normalizedCategory = 'demand';
  else if (normalizedCategory.includes('거시') || normalizedCategory.includes('경제')) normalizedCategory = 'macro';
  else if (normalizedCategory.includes('기후') || normalizedCategory.includes('esg')) normalizedCategory = 'climate';
  else if (normalizedCategory.includes('투기') || normalizedCategory.includes('심리') || normalizedCategory.includes('기술')) normalizedCategory = 'speculation';
  else if (normalizedCategory === '기타') normalizedCategory = 'other';
  
  const isKnown = normalizedCategory in categoryDisplay;
  const badgeClass = isKnown ? normalizedCategory : 'other';
  const text = children || categoryDisplay[badgeClass] || '기타';

  return (
    <span className={`badge badge-${badgeClass} ${className || ''}`}>
      {text}
    </span>
  );
};
