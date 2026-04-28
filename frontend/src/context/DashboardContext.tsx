import { createContext, useState, useContext } from 'react';
import type { ReactNode } from 'react';

type Category = 'geopolitics' | 'supply' | 'demand' | 'macro' | 'climate' | 'speculation';

interface DateRange {
  start: string;
  end: string;
}

interface DashboardContextType {
  selectedDate: string | null;
  setSelectedDate: (date: string | null) => void;
  selectedDateRange: DateRange | null;
  setSelectedDateRange: (range: DateRange | null) => void;
  highlightedCategory: Category | null;
  setHighlightedCategory: (category: Category | null) => void;
}

const DashboardContext = createContext<DashboardContextType | undefined>(undefined);

export const DashboardProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [selectedDate, setSelectedDateState] = useState<string | null>(null);
  const [selectedDateRange, setSelectedDateRangeState] = useState<DateRange | null>(null);
  const [highlightedCategory, setHighlightedCategory] = useState<Category | null>(null);

  // Helper wrappers to ensure mutual exclusivity
  const setSelectedDate = (date: string | null) => {
    setSelectedDateState(date);
    if (date) setSelectedDateRangeState(null);
  };

  const setSelectedDateRange = (range: DateRange | null) => {
    setSelectedDateRangeState(range);
    if (range) setSelectedDateState(null);
  };

  return (
    <DashboardContext.Provider value={{
      selectedDate,
      setSelectedDate,
      selectedDateRange,
      setSelectedDateRange,
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
