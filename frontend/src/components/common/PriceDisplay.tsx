import React from 'react';
import './PriceDisplay.css';

interface PriceDisplayProps {
  value: number;
  change?: number;
  unit?: string;
  className?: string;
  size?: 'small' | 'medium' | 'large';
}

export const PriceDisplay: React.FC<PriceDisplayProps> = ({ value, change, unit = '$', className, size = 'medium' }) => {
  const changeDirection = change === undefined || change === 0 ? 'neutral' : change > 0 ? 'bull' : 'bear';
  const formattedChange = change !== undefined ? `${change > 0 ? '+' : ''}${change.toFixed(2)}` : null;

  return (
    <div className={`price-display price-display-${size} ${className || ''}`}>
      <span className="price-value tabular-nums">{unit}{value.toFixed(2)}</span>
      {formattedChange && (
        <span className={`price-change tabular-nums price-${changeDirection}`}>
          {formattedChange} ({change !== undefined && change !== 0 ? (Math.abs(change) / (value - change) * 100).toFixed(2) : '0.00'}%)
        </span>
      )}
    </div>
  );
};
