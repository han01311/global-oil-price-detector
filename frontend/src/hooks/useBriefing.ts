import { useState, useEffect, useCallback } from 'react';
import { fetchTodayBriefing, fetchBriefingHistory } from '../services/api';
import type { Briefing } from '../types/forecast';

export function useBriefing() {
  const [briefings, setBriefings] = useState<Briefing[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const loadBriefings = async () => {
      try {
        setLoading(true);
        // Fetch today's and the last 7 days of briefings
        const [today, history] = await Promise.all([
          fetchTodayBriefing(),
          fetchBriefingHistory(7),
        ]);

        // Combine and deduplicate, keeping today's as the definitive one if dates match
        const allBriefingsMap = new Map<string, Briefing>();
        allBriefingsMap.set(today.date, today);
        history.forEach(h => {
          if (!allBriefingsMap.has(h.date)) {
            allBriefingsMap.set(h.date, h);
          }
        });

        const allBriefings = Array.from(allBriefingsMap.values());
        
        // Sort by date descending
        allBriefings.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

        setBriefings(allBriefings);
        setCurrentIndex(0);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Failed to fetch briefing data'));
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadBriefings();
  }, []);

  const goToPrevious = useCallback(() => {
    setCurrentIndex(prev => Math.min(prev + 1, briefings.length - 1));
  }, [briefings.length]);

  const goToNext = useCallback(() => {
    setCurrentIndex(prev => Math.max(prev - 1, 0));
  }, []);

  const hasPrevious = currentIndex < briefings.length - 1;
  const hasNext = currentIndex > 0;
  const currentBriefing = briefings[currentIndex];

  return {
    currentBriefing,
    loading,
    error,
    goToPrevious,
    goToNext,
    hasPrevious,
    hasNext,
  };
}
