import { useState, useEffect, useCallback } from 'react';
import { fetchFactorSummary } from '../services/api';
import type { FactorSummary } from '../types/news';

export function useFactorSummary() {
  const [summary, setSummary] = useState<FactorSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  const loadSummary = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const summaryData = await fetchFactorSummary();
      setSummary(summaryData);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch factor summary'));
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSummary();
    // Refetch every 5 minutes
    const intervalId = setInterval(loadSummary, 60000 * 5);
    return () => clearInterval(intervalId);
  }, [loadSummary]);

  return { summary, loading, error, refetch: loadSummary };
}
