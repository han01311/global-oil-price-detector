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
  
  if (normalizedCategory === '기타') {
    normalizedCategory = 'other';
  }
  
  const isKnown = normalizedCategory in categoryDisplay;
  const badgeClass = isKnown ? normalizedCategory : 'other';
  const text = children || categoryDisplay[badgeClass] || '기타';

  return (
    <span className={`badge badge-${badgeClass} ${className || ''}`}>
      {text}
    </span>
  );
};
