import React from 'react';
import './Tooltip.css';

interface TooltipProps {
  content: string;
  children: React.ReactNode;
}

const InfoIcon: React.FC = () => (
  <svg
    className="tooltip-icon"
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <circle cx="8" cy="8" r="6.5" />
    <line x1="8" y1="7" x2="8" y2="11" />
    <line x1="8" y1="5" x2="8" y2="5.5" />
  </svg>
);

export const Tooltip: React.FC<TooltipProps> = ({ content, children }) => {
  return (
    <span className="tooltip-wrapper">
      <span className="tooltip-trigger">
        {children}
        <InfoIcon />
      </span>
      <span className="tooltip-content">{content}</span>
    </span>
  );
};
