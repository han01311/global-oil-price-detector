import React from 'react';
import './Skeleton.css';

interface SkeletonProps {
  className?: string;
  width?: string;
  height?: string;
  style?: React.CSSProperties;
}

export const Skeleton: React.FC<SkeletonProps> = ({ className, width, height, style }) => {
  const customStyle = {
    width: width || '100%',
    height: height || '1rem',
    ...style,
  };
  return <div className={`skeleton ${className || ''}`} style={customStyle}></div>;
};
