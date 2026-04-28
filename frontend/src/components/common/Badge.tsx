import React from 'react';
import './Badge.css';

type Category = 'all' | 'geopolitics' | 'supply' | 'demand' | 'macro' | 'climate' | 'speculation' | 'other' | 'default';

interface BadgeProps {
  category: Category;
  children?: React.ReactNode;
  className?: string;
}

const categoryDisplay: Record<Category, string> = {
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
  const normalizedCategory = (category || 'default').toString().toLowerCase() as Category;
  const text = children || categoryDisplay[normalizedCategory] || categoryDisplay.default;
  return (
    <span className={`badge badge-${normalizedCategory} ${className || ''}`}>
      {text}
    </span>
  );
};
