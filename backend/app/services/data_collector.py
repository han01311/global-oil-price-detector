import asyncio
import json
import logging
import os
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
from hashlib import sha256

import httpx
import pandas as pd
from app.core.config import settings
from app.schemas.price import PriceHistory, OilPrice, MacroHistory, MacroIndicator

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

class BaseCollector:
    """외부 API 호출을 위한 기본 클래스"""
    cache_dir = os.path.join(settings.DATA_CACHE_DIR, "raw")

    def __init__(self, api_key: str | None, base_url: str):
        if not api_key:
            # Allow collectors that don't need a key (like GDELT)
            pass
        self.api_key = api_key
        self.base_url = base_url
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, name: str) -> str:
        today = datetime.now().strftime('%Y-%m-%d')
        return os.path.join(self.cache_dir, f"{today}_{name}.json")

    async def _fetch_api(self, endpoint: str, params: dict, cache_name: str) -> dict:
        cache_path = self._get_cache_path(cache_name)
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                return json.load(f)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}{endpoint}", params=params)
                response.raise_for_status()
                data = response.json()

                with open(cache_path, 'w') as f:
                    json.dump(data, f)
                return data
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error fetching {e.request.url}: {e.response.status_code}")
                raise
            except Exception as e:
                logger.error(f"Error fetching {self.base_url}{endpoint}: {e}")
                raise

class EIACollector(BaseCollector):
    SERIES_IDS = {
        "wti": "PET.RWTC.D",
        "brent": "PET.RBRTE.D",
        "inventory": "PET.WCESTUS1.W",
        "production": "PET.WCRFPUS2.W",
    }

    def __init__(self, api_key: str | None = settings.EIA_API_KEY):
        if not api_key:
            raise ValueError("EIA_API_KEY is required for EIACollector.")
        super().__init__(api_key, "https://api.eia.gov/v2")

    async def _get_series_data(self, series_id: str, start: str, end: str) -> List[Dict]:
        params = {
            "api_key": self.api_key,
            "frequency": "daily" if ".D" in series_id else "weekly",
            "data[0]": "value",
            "facets[seriesId][]": series_id,
            "start": start,
            "end": end,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "offset": 0,
            "length": 5000,
        }
        data = await self._fetch_api("/petroleum/pri/spt/data/", params, series_id)
        return data.get("response", {}).get("data", [])

    async def get_crude_prices(self, start_date: str, end_date: str) -> pd.DataFrame:
        wti_data, brent_data = await asyncio.gather(
            self._get_series_data(self.SERIES_IDS["wti"], start_date, end_date),
            self._get_series_data(self.SERIES_IDS["brent"], start_date, end_date)
        )
        wti_df = pd.DataFrame(wti_data)[['period', 'value']].rename(columns={'period': 'date', 'value': 'wti'}) if wti_data else pd.DataFrame(columns=['date', 'wti'])
        brent_df = pd.DataFrame(brent_data)[['period', 'value']].rename(columns={'period': 'date', 'value': 'brent'}) if brent_data else pd.DataFrame(columns=['date', 'brent'])
        
        if wti_df.empty and brent_df.empty:
             return pd.DataFrame(columns=['date', 'wti', 'brent'])

        df = pd.merge(wti_df, brent_df, on='date', how='outer')
        df[['wti', 'brent']] = df[['wti', 'brent']].astype(float)
        return df

class FREDCollector(BaseCollector):
    MACRO_SERIES = {
        "fed_rate": "FEDFUNDS",
        "dollar_index": "DTWEXBGS",
    }
    def __init__(self, api_key: str | None = settings.FRED_API_KEY):
        if not api_key:
            raise ValueError("FRED_API_KEY is required for FREDCollector.")
        super().__init__(api_key, "https://api.stlouisfed.org/fred")

    async def get_series(self, series_id: str, col_name: str, start_date: str, end_date: str) -> pd.DataFrame:
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start_date,
            "observation_end": end_date,
        }
        data = await self._fetch_api("/series/observations", params, series_id)
        obs = data.get("observations", [])
        if not obs:
            return pd.DataFrame(columns=['date', col_name])
        df = pd.DataFrame(obs)[['date', 'value']]
        df = df[df['value'] != "."]
        df = df.rename(columns={'value': col_name})
        df[col_name] = df[col_name].astype(float)
        return df

    async def get_macro_indicators(self, start_date: str, end_date: str) -> pd.DataFrame:
        tasks = [self.get_series(series_id, name, start_date, end_date) for name, series_id in self.MACRO_SERIES.items()]
        results = await asyncio.gather(*tasks)
        
        merged_df = pd.DataFrame(pd.date_range(start=start_date, end=end_date), columns=['date'])
        merged_df['date'] = merged_df['date'].dt.strftime('%Y-%m-%d')

        for df in results:
            if not df.empty:
                merged_df = pd.merge(merged_df, df, on='date', how='left')
        
        merged_df = merged_df.ffill().dropna()
        return merged_df

class NewsCollector:
    KEYWORDS = ["crude oil", "WTI", "Brent", "OPEC", "shale oil", "oil demand", "oil supply", "oil reserves", "geopolitics oil"]
    cache_dir = os.path.join(settings.DATA_CACHE_DIR, "raw")

    def __init__(self, news_api_key: str | None = settings.NEWS_API_KEY):
        self.news_api_key = news_api_key
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, name: str) -> str:
        today = datetime.now().strftime('%Y-%m-%d')
        return os.path.join(self.cache_dir, f"{today}_{name}.json")

    async def get_latest_news(self) -> List[Dict[str, Any]]:
        if not self.news_api_key:
            return []
        
        cache_path = self._get_cache_path("newsapi")
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                return json.load(f).get("articles", [])

        query = " OR ".join([f'"{k}"' for k in self.KEYWORDS])
        params = {
            "q": query, "language": "en", "sortBy": "publishedAt", "apiKey": self.news_api_key, "pageSize": 50
        }
        async with httpx.AsyncClient() as client:
            response = await client.get("https://newsapi.org/v2/everything", params=params)
            response.raise_for_status()
            data = response.json()
            with open(cache_path, 'w') as f:
                json.dump(data, f)
            return data.get("articles", [])

    async def get_gdelt_events(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        cache_path = self._get_cache_path(f"gdelt_{start_date}_{end_date}")
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                return json.load(f).get("articles", [])
        
        query = " OR ".join([f'"{k}"' for k in self.KEYWORDS])
        start = datetime.fromisoformat(start_date).strftime('%Y%m%d000000')
        end = datetime.fromisoformat(end_date).strftime('%Y%m%d235959')
        params = {
            "query": query, "mode": "artlist", "format": "json", "maxrecords": 50,
            "startdatetime": start, "enddatetime": end
        }
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.gdeltproject.org/api/v2/doc/doc", params=params)
            response.raise_for_status()
            data = response.json()
            with open(cache_path, 'w') as f:
                json.dump(data, f)
            return data.get("articles", [])

class DataCollector:
    def __init__(self):
        self.eia = EIACollector() if settings.EIA_API_KEY else None
        self.fred = FREDCollector() if settings.FRED_API_KEY else None
        self.news = NewsCollector()

    async def collect_prices(self, start_date: str, end_date: str) -> PriceHistory:
        if not self.eia:
            return PriceHistory(prices=[], source="eia", last_updated=datetime.now().isoformat())
        df = await self.eia.get_crude_prices(start_date, end_date)
        prices = [OilPrice(**row) for _, row in df.iterrows()]
        return PriceHistory(prices=prices, source="eia", last_updated=datetime.now().isoformat())

    async def collect_macro_data(self, start_date: str, end_date: str) -> MacroHistory:
        if not self.fred:
            return MacroHistory(indicators=[], source="fred", last_updated=datetime.now().isoformat())
        df = await self.fred.get_macro_indicators(start_date, end_date)
        indicators = [MacroIndicator(**row) for _, row in df.iterrows()]
        return MacroHistory(indicators=indicators, source="fred", last_updated=datetime.now().isoformat())

    def _normalize_article(self, article: Dict, source: str) -> Dict:
        if source == "newsapi":
            content = article.get('content') or article.get('description') or ''
            return {
                "id": sha256(article['url'].encode()).hexdigest(),
                "title": article['title'], "description": article.get('description'),
                "source": article.get('source', {}).get('name'), "url": article['url'],
                "published_at": article['publishedAt'], "content_snippet": content[:200] if content else None,
                "data_source": "newsapi"
            }
        elif source == "gdelt":
            pub_date = datetime.strptime(article['seendate'], '%Y%m%d%H%M%S').isoformat() + "Z"
            return {
                "id": sha256(article['url'].encode()).hexdigest(),
                "title": article['title'], "description": None,
                "source": article.get('domain'), "url": article['url'],
                "published_at": pub_date, "content_snippet": None,
                "data_source": "gdelt"
            }
        return {}

    async def collect_news(self) -> List[Dict[str, Any]]:
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        
        newsapi_task = self.news.get_latest_news()
        gdelt_task = self.news.get_gdelt_events(yesterday, today)
        
        newsapi_articles, gdelt_articles = await asyncio.gather(newsapi_task, gdelt_task)
        
        all_articles = []
        seen_urls = set()

        for article in (newsapi_articles or []):
            if article.get('url') and article['url'] not in seen_urls:
                all_articles.append(self._normalize_article(article, "newsapi"))
                seen_urls.add(article['url'])
        
        for article in (gdelt_articles or []):
            if article.get('url') and article['url'] not in seen_urls:
                all_articles.append(self._normalize_article(article, "gdelt"))
                seen_urls.add(article['url'])
        
        return all_articles

    async def collect_all(self, start_date: str, end_date: str) -> Dict:
        prices, macro, news = await asyncio.gather(
            self.collect_prices(start_date, end_date),
            self.collect_macro_data(start_date, end_date),
            self.collect_news()
        )
        return {"prices": prices, "macro": macro, "news": news}

    async def collect_latest_prices(self) -> PriceHistory | None:
        end_date = date.today()
        start_date = end_date - timedelta(days=10)
        return await self.collect_prices(start_date.isoformat(), end_date.isoformat())

    async def collect_prices_df_for_features(self) -> pd.DataFrame:
        end_date = date.today()
        start_date = end_date - timedelta(days=100)
        price_history = await self.collect_prices(start_date.isoformat(), end_date.isoformat())
        if not price_history or not price_history.prices:
            return pd.DataFrame()
        return pd.DataFrame([p.model_dump() for p in price_history.prices])

    async def collect_macro_df_for_features(self) -> pd.DataFrame:
        end_date = date.today()
        start_date = end_date - timedelta(days=100)
        macro_history = await self.collect_macro_data(start_date.isoformat(), end_date.isoformat())
        if not macro_history or not macro_history.indicators:
            return pd.DataFrame()
        return pd.DataFrame([i.model_dump() for i in macro_history.indicators])
