import React from 'react';
import { useToastContext } from '../../context/ToastContext';
import type { ToastItem } from '../../context/ToastContext';
import './Toast.css';

const ToastIcon: React.FC<{ type: ToastItem['type'] }> = ({ type }) => {
  const paths: Record<string, string> = {
    info: 'M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 3.5v1m0 2v4',
    success: 'M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm-2 7l2 2 4-4',
    warning: 'M8 1.5L1 14h14L8 1.5zM8 6v4m0 2v1',
    error: 'M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm-2.5 4.5l5 5m0-5l-5 5',
  };
  return (
    <svg className="toast-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d={paths[type]} />
    </svg>
  );
};

export const ToastRenderer: React.FC = () => {
  const { toasts, removeToast } = useToastContext();

  if (toasts.length === 0) return null;

  return (
    <div className="toast-container" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast-item toast-${t.type}`}>
          <ToastIcon type={t.type} />
          <span className="toast-message">{t.message}</span>
          <button className="toast-close" onClick={() => removeToast(t.id)} aria-label="닫기">
            &times;
          </button>
        </div>
      ))}
    </div>
  );
};
