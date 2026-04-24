import { useState, useEffect } from 'react';
import { fetchFactorSummary } from '../services/api';
import { FactorSummary } from '../types/news';

export function useFactorSummary() {
  const [summary, setSummary] = useState<FactorSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const loadSummary = async () => {
      try {
        setLoading(true);
        const summaryData = await fetchFactorSummary();
        setSummary(summaryData);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Failed to fetch factor summary'));
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadSummary();
    // Refetch every 5 minutes
    const intervalId = setInterval(loadSummary, 60000 * 5);
    return () => clearInterval(intervalId);
  }, []);

  return { summary, loading, error };
}
