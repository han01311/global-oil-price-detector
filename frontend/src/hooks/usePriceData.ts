import { useState, useEffect, useMemo } from 'react';
import { fetchPriceHistory, fetchForecastEstimate, fetchAndClassifyNews, fetchNewsDateCounts } from '../services/api';
import type { OilPrice } from '../types/price';
import type { ForecastResult } from '../types/forecast';
import type { ClassifiedArticle } from '../types/news';
import type { NewsDateCount } from '../services/api';

export type Period = '1M' | '3M' | '6M' | '1Y' | 'ALL';

export interface ChartDataPoint {
  date: string;
  timestamp: number;
  dubai: number | null;
  wti: number | null;
  brent: number | null;
  forecastLine?: number;
  forecastBand?: [number, number];
  article?: ClassifiedArticle;
  dbArticleCount?: number;
  filterDate?: string;
}

export interface NewsMarker {
  timestamp: number;
  value: number;
  article: ClassifiedArticle;
}

export interface DBNewsMarker {
  timestamp: number;
  value: number;
  date: string;
  count: number;
}

interface PriceData {
  chartData: ChartDataPoint[];
  newsMarkers: NewsMarker[];
  dbNewsMarkers: DBNewsMarker[];
  forecast: ForecastResult | null;
  rawNewsCounts: Record<string, number>;
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
  const [newsDateCounts, setNewsDateCounts] = useState<NewsDateCount[]>([]);
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
        case 'ALL': startDate.setFullYear(endDate.getFullYear() - 30); break; // Max 30 years for 'ALL'
      }
      return startDate.toISOString().split('T')[0];
    };

    const loadData = async () => {
      try {
        setLoading(true);
        const startDate = getStartDate(period);
        const endDate = new Date().toISOString().split('T')[0];

        const [historyData, forecastData, newsData, dateCountsData] = await Promise.all([
          fetchPriceHistory(startDate, endDate),
          fetchForecastEstimate(),
          fetchAndClassifyNews().catch(() => []),
          fetchNewsDateCounts(startDate, endDate).catch(() => []),
        ]);

        setHistory(historyData.prices);
        setForecast(forecastData);
        setNews(newsData);
        setNewsDateCounts(dateCountsData);
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

  const { chartData, newsMarkers, dbNewsMarkers, rawNewsCounts } = useMemo(() => {
    if (!history.length) {
      return { chartData: [], newsMarkers: [], dbNewsMarkers: [] };
    }

    const dateCountMap = new Map<string, number>();
    newsDateCounts.forEach(dc => dateCountMap.set(dc.date, dc.count));

    const processedChartData: ChartDataPoint[] = [];
    const lastValid = { dubai: null as number | null, wti: null as number | null, brent: null as number | null };

    history.forEach(p => {
      const dubai = (p.dubai && p.dubai !== 0) ? p.dubai : lastValid.dubai;
      const wti = (p.wti && p.wti !== 0) ? p.wti : lastValid.wti;
      const brent = (p.brent && p.brent !== 0) ? p.brent : lastValid.brent;

      if (dubai && dubai !== 0) lastValid.dubai = dubai;
      if (wti && wti !== 0) lastValid.wti = wti;
      if (brent && brent !== 0) lastValid.brent = brent;

      const dbCount = dateCountMap.get(p.date) || 0;

      processedChartData.push({
        date: p.date,
        timestamp: new Date(p.date).getTime(),
        dubai,
        wti,
        brent,
        dbArticleCount: dbCount > 0 ? dbCount : undefined,
      });
    });

    if (forecast && processedChartData.length > 0) {
      const lastDataPoint = processedChartData[processedChartData.length - 1];
      const lastDate = new Date(lastDataPoint.date);

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

    // Classified 뉴스 마커 (LLM 분류)
    const processedNewsMarkers: NewsMarker[] = news
      .filter(n => n.is_relevant)
      .map(n => {
        const date = n.article.published_at.split('T')[0];
        const chartPoint = processedChartData.find(d => d.date === date);
        if (!chartPoint || chartPoint.wti === null) return null;
        return { timestamp: chartPoint.timestamp, value: chartPoint.wti, article: n };
      })
      .filter((n): n is NewsMarker => n !== null);

    // DB 기사 마커 (날짜에 기사가 있는 포인트)
    const processedDBMarkers: DBNewsMarker[] = [];
    processedChartData.forEach(point => {
      if (point.dbArticleCount && point.dbArticleCount > 0 && point.wti !== null) {
        processedDBMarkers.push({
          timestamp: point.timestamp,
          value: point.wti,
          date: point.date,
          count: point.dbArticleCount,
        });
      }
    });

    // Add classified articles to chart data for tooltip
    const chartDataMap = new Map<number, ChartDataPoint>(processedChartData.map(d => [d.timestamp, d]));
    processedNewsMarkers.forEach(marker => {
      if (chartDataMap.has(marker.timestamp)) {
        chartDataMap.get(marker.timestamp)!.article = marker.article;
      }
    });

    const rawNewsCounts: Record<string, number> = {};
    dateCountMap.forEach((val, key) => { rawNewsCounts[key] = val; });

    return {
      chartData: Array.from(chartDataMap.values()),
      newsMarkers: processedNewsMarkers,
      dbNewsMarkers: processedDBMarkers,
      rawNewsCounts,
    };
  }, [history, forecast, news, newsDateCounts]);

  return { chartData, newsMarkers, dbNewsMarkers, rawNewsCounts, forecast, loading, error };
}

export { getCategoryColor };
