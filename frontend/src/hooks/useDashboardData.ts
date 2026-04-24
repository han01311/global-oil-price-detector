import { useState, useEffect } from 'react';
import { fetchLatestPrice, fetchForecastEstimate } from '../services/api';
import { OilPrice } from '../types/price';
import { ForecastResult } from '../types/forecast';

interface DashboardData {
  latestPrice: (OilPrice & { change?: number }) | null;
  forecast: ForecastResult | null;
  loading: boolean;
  error: Error | null;
}

export function useDashboardData(): DashboardData {
  const [latestPrice, setLatestPrice] = useState<(OilPrice & { change?: number }) | null>(null);
  const [forecast, setForecast] = useState<ForecastResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        // In a real app, you might want to avoid fetching forecast just for the price change,
        // but for this dashboard it's a core piece of data.
        const [priceData, forecastData] = await Promise.all([
          fetchLatestPrice(),
          fetchForecastEstimate(),
        ]);

        // The change is calculated against the previous day's close, which is `current_price` in the forecast.
        const change = priceData.wti && forecastData.current_price
          ? priceData.wti - forecastData.current_price
          : undefined;

        setLatestPrice({ ...priceData, change });
        setForecast(forecastData);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Failed to fetch dashboard data'));
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  return { latestPrice, forecast, loading, error };
}
