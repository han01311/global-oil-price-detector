import { createContext, useState, useContext } from 'react';
import type { ReactNode } from 'react';

type Category = 'geopolitics' | 'supply' | 'demand' | 'macro' | 'climate' | 'speculation';

interface DashboardContextType {
  selectedDate: string | null;
  setSelectedDate: (date: string | null) => void;
  highlightedCategory: Category | null;
  setHighlightedCategory: (category: Category | null) => void;
}

const DashboardContext = createContext<DashboardContextType | undefined>(undefined);

export const DashboardProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [highlightedCategory, setHighlightedCategory] = useState<Category | null>(null);

  return (
    <DashboardContext.Provider value={{
      selectedDate,
      setSelectedDate,
      highlightedCategory,
      setHighlightedCategory
    }}>
      {children}
    </DashboardContext.Provider>
  );
};

export const useDashboardContext = (): DashboardContextType => {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error('useDashboardContext must be used within a DashboardProvider');
  }
  return context;
};
