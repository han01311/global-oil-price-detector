import { createContext, useState, useCallback, useContext } from 'react';
import type { ReactNode } from 'react';

export interface ToastItem {
  id: number;
  type: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

interface ToastContextType {
  toasts: ToastItem[];
  addToast: (type: ToastItem['type'], message: string) => void;
  removeToast: (id: number) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

let nextToastId = 0;

export const ToastProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback((type: ToastItem['type'], message: string) => {
    const id = nextToastId++;
    setToasts((prev) => [...prev, { id, type, message }]);

    // Auto-remove after 3 seconds
    setTimeout(() => {
      removeToast(id);
    }, 3000);
  }, [removeToast]);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
    </ToastContext.Provider>
  );
};

export const useToastContext = (): ToastContextType => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToastContext must be used within a ToastProvider');
  }
  return context;
};

/** Convenience hook for components */
export function useToast() {
  const { addToast } = useToastContext();
  return {
    info: (message: string) => addToast('info', message),
    success: (message: string) => addToast('success', message),
    warning: (message: string) => addToast('warning', message),
    error: (message: string) => addToast('error', message),
  };
}
