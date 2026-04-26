import { useState, useEffect, useMemo } from 'react';
import { fetchPriceHistory, fetchForecastEstimate, fetchAndClassifyNews } from '../services/api';
import type { OilPrice } from '../types/price';
import type { ForecastResult } from '../types/forecast';
import type { ClassifiedArticle } from '../types/news';

export type Period = '1M' | '3M' | '6M' | '1Y' | 'ALL';

export interface ChartDataPoint {
  date: string;
  timestamp: number;
  dubai: number | null;
  wti: number | null;
  brent: number | null;
  forecastLine?: number;
  forecastBand?: [number, number];
  article?: ClassifiedArticle; // For tooltip
}

export interface NewsMarker {
  timestamp: number;
  value: number;
  article: ClassifiedArticle;
}

interface PriceData {
  chartData: ChartDataPoint[];
  newsMarkers: NewsMarker[];
  forecast: ForecastResult | null;
  loading: boolean;
  error: Error | null;
}

const getCategoryColor = (category: string): string => {
  const colorMap: Record<string, string> = {
    geopolitics: 'var(--color-cat-geopolitics)',
    supply: 'var(--color-cat-supply)',
    demand: 'var(--color-cat-demand)',
    macro: 'var(--color-cat-macro)',
    climate: 'var(--color-cat-climate)',
    speculation: 'var(--color-cat-speculation)',
  };
  return colorMap[category] || 'var(--color-neutral)';
};

export function usePriceData(period: Period): PriceData {
  const [history, setHistory] = useState<OilPrice[]>([]);
  const [forecast, setForecast] = useState<ForecastResult | null>(null);
  const [news, setNews] = useState<ClassifiedArticle[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const getStartDate = (period: Period): string => {
      const endDate = new Date();
      let startDate = new Date();

      switch (period) {
        case '1M': startDate.setMonth(endDate.getMonth() - 1); break;
        case '3M': startDate.setMonth(endDate.getMonth() - 3); break;
        case '6M': startDate.setMonth(endDate.getMonth() - 6); break;
        case '1Y': startDate.setFullYear(endDate.getFullYear() - 1); break;
        case 'ALL': startDate.setFullYear(endDate.getFullYear() - 5); break; // Max 5 years for 'ALL'
      }
      return startDate.toISOString().split('T')[0];
    };

    const loadData = async () => {
      try {
        setLoading(true);
        const startDate = getStartDate(period);
        const endDate = new Date().toISOString().split('T')[0];

        const [historyData, forecastData, newsData] = await Promise.all([
          fetchPriceHistory(startDate, endDate),
          fetchForecastEstimate(),
          fetchAndClassifyNews(),
        ]);

        setHistory(historyData.prices);
        setForecast(forecastData);
        setNews(newsData);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Failed to fetch price data'));
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [period]);

  const { chartData, newsMarkers } = useMemo(() => {
    if (!history.length) {
      return { chartData: [], newsMarkers: [] };
    }

    const priceMap = new Map<string, OilPrice>(history.map(p => [p.date, p]));

    const processedChartData: ChartDataPoint[] = [];
    const lastValid = { dubai: null as number | null, wti: null as number | null, brent: null as number | null };

    history.forEach(p => {
      // 값이 없거나 0인 경우 이전의 유효한 값을 사용 (Forward-fill)
      const dubai = (p.dubai && p.dubai !== 0) ? p.dubai : lastValid.dubai;
      const wti = (p.wti && p.wti !== 0) ? p.wti : lastValid.wti;
      const brent = (p.brent && p.brent !== 0) ? p.brent : lastValid.brent;

      // 현재 값이 유효하다면 캐시 업데이트
      if (dubai && dubai !== 0) lastValid.dubai = dubai;
      if (wti && wti !== 0) lastValid.wti = wti;
      if (brent && brent !== 0) lastValid.brent = brent;

      processedChartData.push({
        date: p.date,
        timestamp: new Date(p.date).getTime(),
        dubai: dubai,
        wti: wti,
        brent: brent,
      });
    });

    if (forecast && processedChartData.length > 0) {
      const lastDataPoint = processedChartData[processedChartData.length - 1];
      const lastDate = new Date(lastDataPoint.date);

      // Anchor the forecast band to the last known price
      lastDataPoint.forecastBand = [lastDataPoint.wti!, lastDataPoint.wti!];
      lastDataPoint.forecastLine = lastDataPoint.wti!;

      const futureDate7d = new Date(lastDate);
      futureDate7d.setDate(lastDate.getDate() + 7);

      processedChartData.push({
        date: futureDate7d.toISOString().split('T')[0],
        timestamp: futureDate7d.getTime(),
        dubai: null,
        wti: null,
        brent: null,
        forecastLine: forecast.estimated_7d,
        forecastBand: [forecast.estimated_7d_low, forecast.estimated_7d_high],
      });
    }

    const processedNewsMarkers: NewsMarker[] = news
      .filter(n => n.is_relevant)
      .map(n => {
        const date = n.article.published_at.split('T')[0];
        // Use forward-filled chart data instead of raw history
        const chartPoint = processedChartData.find(d => d.date === date);
        if (!chartPoint || chartPoint.wti === null) return null;

        return {
          timestamp: chartPoint.timestamp,
          value: chartPoint.wti,
          article: n,
        };
      })
      .filter((n): n is NewsMarker => n !== null);

    // Add news articles to the main chart data for tooltip purposes
    const chartDataMap = new Map<number, ChartDataPoint>(processedChartData.map(d => [d.timestamp, d]));
    processedNewsMarkers.forEach(marker => {
      if (chartDataMap.has(marker.timestamp)) {
        chartDataMap.get(marker.timestamp)!.article = marker.article;
      }
    });

    return { chartData: Array.from(chartDataMap.values()), newsMarkers: processedNewsMarkers };
  }, [history, forecast, news]);

  return { chartData, newsMarkers, forecast, loading, error };
}

export { getCategoryColor };
