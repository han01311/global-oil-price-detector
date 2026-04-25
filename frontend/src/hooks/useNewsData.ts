import { useState, useEffect, useCallback } from 'react';
import { fetchAndClassifyNews } from '../services/api';
import type { ClassifiedArticle } from '../types/news';

export function useNewsData() {
  const [articles, setArticles] = useState<ClassifiedArticle[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  const loadNews = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const newsData = await fetchAndClassifyNews();
      // Sort by time initially (most recent first)
      const relevantNews = newsData
        .filter(a => a.is_relevant)
        .sort((a, b) => 
          new Date(b.article.published_at).getTime() - new Date(a.article.published_at).getTime()
        );
      setArticles(relevantNews);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch news data'));
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadNews();
  }, [loadNews]);

  return { articles, loading, error, refetch: loadNews };
}
