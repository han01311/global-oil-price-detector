from __future__ import annotations

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
from app.core.database import Database
from app.schemas.price import PriceHistory, OilPrice, MacroHistory, MacroIndicator
from app.services.rate_limiter import RateLimiter, with_backoff
from app.services.opinet_collector import OpinetCollector

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
        self.rate_limiter = RateLimiter()
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, name: str) -> str:
        today = datetime.now().strftime('%Y-%m-%d')
        return os.path.join(self.cache_dir, f"{today}_{name}.json")

    async def _fetch_api(self, endpoint: str, params: dict, cache_name: str, rate_limit_source: str = "") -> dict:
        """
        외부 API 호출 (캐시 + Rate Limit + Backoff 통합).

        1. 로컬 JSON 캐시 확인
        2. Rate Limiter로 호출 가능 여부 확인
        3. Exponential Backoff로 API 호출
        4. 결과를 JSON 캐시에 저장
        """
        cache_path = self._get_cache_path(cache_name)
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                return json.load(f)

        # Rate Limit 체크
        if rate_limit_source:
            can_proceed = await self.rate_limiter.acquire(rate_limit_source)
            if not can_proceed:
                logger.warning(f"Rate limit exceeded for {rate_limit_source}. Trying fallback cache.")
                return self._find_latest_cache(cache_name)

        # Backoff 래핑된 실제 HTTP 호출
        async def do_fetch():
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}{endpoint}", params=params)
                response.raise_for_status()
                return response.json()

        try:
            source_name = rate_limit_source or "unknown"
            data = await with_backoff(source_name, do_fetch)

            with open(cache_path, 'w') as f:
                json.dump(data, f)
            return data

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching {e.request.url}: {e.response.status_code}")
            # Fallback: 가장 최근 캐시 사용
            fallback = self._find_latest_cache(cache_name)
            if fallback:
                logger.info(f"Using fallback cache for {cache_name}")
                return fallback
            raise
        except Exception as e:
            logger.error(f"Error fetching {self.base_url}{endpoint}: {e}")
            fallback = self._find_latest_cache(cache_name)
            if fallback:
                logger.info(f"Using fallback cache for {cache_name}")
                return fallback
            raise

    def _find_latest_cache(self, cache_name: str) -> dict:
        """가장 최근의 캐시 파일을 찾아 반환 (Fallback용)"""
        try:
            files = []
            for f in os.listdir(self.cache_dir):
                if f.endswith(f"_{cache_name}.json"):
                    files.append(os.path.join(self.cache_dir, f))
            if not files:
                return {}
            latest = max(files, key=os.path.getmtime)
            with open(latest, 'r') as f:
                logger.info(f"[Fallback] Loading cached data from {latest}")
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load fallback cache for {cache_name}: {e}")
            return {}


class EIACollector(BaseCollector):
    SERIES_IDS = {
        "wti": "RWTC",
        "brent": "RBRTE",
        "inventory": "WCESTUS1",
        "production": "WCRFPUS2",
    }

    def __init__(self, api_key: str | None = None):
        api_key = api_key or settings.EIA_API_KEY
        if not api_key:
            raise ValueError("EIA_API_KEY is required for EIACollector.")
        super().__init__(api_key, "https://api.eia.gov/v2")

    async def _get_series_data(self, endpoint: str, frequency: str, series_id: str, start: str, end: str) -> List[Dict]:
        params = {
            "api_key": self.api_key,
            "frequency": frequency,
            "data[0]": "value",
            "facets[series][]": series_id,
            "start": start,
            "end": end,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "offset": 0,
            "length": 5000,
        }
        data = await self._fetch_api(endpoint, params, series_id, rate_limit_source="eia")
        return data.get("response", {}).get("data", [])

    async def get_crude_prices(self, start_date: str, end_date: str) -> pd.DataFrame:
        wti_data, brent_data = await asyncio.gather(
            self._get_series_data("/petroleum/pri/spt/data/", "daily", self.SERIES_IDS["wti"], start_date, end_date),
            self._get_series_data("/petroleum/pri/spt/data/", "daily", self.SERIES_IDS["brent"], start_date, end_date)
        )
        wti_df = pd.DataFrame(wti_data)[['period', 'value']].rename(columns={'period': 'date', 'value': 'wti'}) if wti_data else pd.DataFrame(columns=['date', 'wti'])
        brent_df = pd.DataFrame(brent_data)[['period', 'value']].rename(columns={'period': 'date', 'value': 'brent'}) if brent_data else pd.DataFrame(columns=['date', 'brent'])
        
        if wti_df.empty and brent_df.empty:
             return pd.DataFrame(columns=['date', 'wti', 'brent'])

        df = pd.merge(wti_df, brent_df, on='date', how='outer')
        df[['wti', 'brent']] = df[['wti', 'brent']].astype(float)
        return df

    async def get_crude_inventory(self, start_date: str, end_date: str) -> pd.DataFrame:
        data = await self._get_series_data("/petroleum/stoc/wstk/data/", "weekly", self.SERIES_IDS["inventory"], start_date, end_date)
        if not data:
            return pd.DataFrame(columns=['date', 'inventory_mbbl'])
        df = pd.DataFrame(data)[['period', 'value']].rename(columns={'period': 'date', 'value': 'inventory_mbbl'})
        df['inventory_mbbl'] = df['inventory_mbbl'].astype(float)
        return df

    async def get_production(self, start_date: str, end_date: str) -> pd.DataFrame:
        data = await self._get_series_data("/petroleum/sum/sndw/data/", "weekly", self.SERIES_IDS["production"], start_date, end_date)
        if not data:
            return pd.DataFrame(columns=['date', 'production_mbbl_d'])
        df = pd.DataFrame(data)[['period', 'value']].rename(columns={'period': 'date', 'value': 'production_mbbl_d'})
        df['production_mbbl_d'] = df['production_mbbl_d'].astype(float)
        return df


class FREDCollector(BaseCollector):
    MACRO_SERIES = {
        "fed_rate": "FEDFUNDS",
        "dollar_index": "DTWEXBGS",
    }
    def __init__(self, api_key: str | None = None):
        api_key = api_key or settings.FRED_API_KEY
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
        data = await self._fetch_api("/series/observations", params, series_id, rate_limit_source="fred")
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
        
        all_dates = set()
        for df in results:
            if not df.empty:
                all_dates.update(df['date'].tolist())
        
        if not all_dates:
             return pd.DataFrame(columns=['date', 'fed_rate', 'dollar_index'])
             
        merged_df = pd.DataFrame(sorted(list(all_dates)), columns=['date'])

        for df in results:
            if not df.empty:
                merged_df = pd.merge(merged_df, df, on='date', how='outer')
        
        merged_df = merged_df.sort_values('date').ffill().bfill()
        merged_df = merged_df[(merged_df['date'] >= start_date) & (merged_df['date'] <= end_date)]
        return merged_df


class NewsCollector:
    """NewsAPI 뉴스 수집기"""
    KEYWORDS = ["crude oil", "WTI", "Brent", "OPEC", "shale oil", "oil demand", "oil supply", "oil reserves", "geopolitics oil"]
    cache_dir = os.path.join(settings.DATA_CACHE_DIR, "raw")

    def __init__(self, news_api_key: str | None = None):
        self.news_api_key = news_api_key or settings.NEWS_API_KEY
        self.rate_limiter = RateLimiter()
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

        # Rate Limit 체크 (100회/일)
        can_proceed = await self.rate_limiter.acquire("newsapi")
        if not can_proceed:
            logger.warning("NewsAPI daily limit reached. Skipping.")
            return []

        query = " OR ".join([f'"{k}"' for k in self.KEYWORDS])
        params = {
            "q": query, "language": "en", "sortBy": "publishedAt", "apiKey": self.news_api_key, "pageSize": 50
        }

        async def do_fetch():
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get("https://newsapi.org/v2/everything", params=params)
                response.raise_for_status()
                return response.json()

        try:
            data = await with_backoff("newsapi", do_fetch)
            with open(cache_path, 'w') as f:
                json.dump(data, f)
            return data.get("articles", [])
        except Exception as e:
            logger.error(f"NewsAPI fetch failed: {e}")
            return []

    async def get_gdelt_events(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        cache_path = self._get_cache_path(f"gdelt_{start_date}_{end_date}")
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                return json.load(f).get("articles", [])

        # Rate Limit 체크 (6초 간격)
        can_proceed = await self.rate_limiter.acquire("gdelt")
        if not can_proceed:
            return []

        query = " OR ".join([f'"{k}"' for k in self.KEYWORDS])
        start = datetime.fromisoformat(start_date).strftime('%Y%m%d000000')
        end = datetime.fromisoformat(end_date).strftime('%Y%m%d235959')
        params = {
            "query": query, "mode": "artlist", "format": "json", "maxrecords": 50,
            "startdatetime": start, "enddatetime": end
        }

        async def do_fetch():
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get("https://api.gdeltproject.org/api/v2/doc/doc", params=params)
                response.raise_for_status()
                return response.json()

        try:
            data = await with_backoff("gdelt", do_fetch)
            with open(cache_path, 'w') as f:
                json.dump(data, f)
            return data.get("articles", [])
        except Exception as e:
            logger.error(f"GDELT fetch failed: {e}")
            return []


class GNewsCollector:
    """GNews API 뉴스 수집기 (NewsAPI 보완용)"""
    KEYWORDS = ["crude oil price", "OPEC production", "oil market", "WTI Brent"]
    cache_dir = os.path.join(settings.DATA_CACHE_DIR, "raw")

    def __init__(self, gnews_api_key: str | None = None):
        self.gnews_api_key = gnews_api_key or settings.GNEWS_API_KEY
        self.rate_limiter = RateLimiter()
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, name: str) -> str:
        today = datetime.now().strftime('%Y-%m-%d')
        return os.path.join(self.cache_dir, f"{today}_{name}.json")

    async def get_latest_news(self) -> List[Dict[str, Any]]:
        """GNews에서 최신 유가 관련 뉴스를 수집한다."""
        if not self.gnews_api_key:
            logger.debug("GNews API key not configured. Skipping.")
            return []

        cache_path = self._get_cache_path("gnews")
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                return json.load(f).get("articles", [])

        # Rate Limit 체크 (100회/일, 10건/요청)
        can_proceed = await self.rate_limiter.acquire("gnews")
        if not can_proceed:
            logger.warning("GNews daily limit reached. Skipping.")
            return []

        all_articles: List[Dict] = []
        for keyword in self.KEYWORDS:
            # 각 키워드마다 Rate Limit 체크
            can_proceed = await self.rate_limiter.acquire("gnews")
            if not can_proceed:
                break

            params = {
                "q": keyword,
                "lang": "en",
                "max": 10,  # 무료 플랜 최대
                "apikey": self.gnews_api_key,
            }

            try:
                async def do_fetch():
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.get("https://gnews.io/api/v4/search", params=params)
                        response.raise_for_status()
                        return response.json()

                data = await with_backoff("gnews", do_fetch)
                articles = data.get("articles", [])
                all_articles.extend(articles)
            except Exception as e:
                logger.error(f"GNews fetch failed for keyword '{keyword}': {e}")
                continue

        # 캐시 저장
        if all_articles:
            with open(cache_path, 'w') as f:
                json.dump({"articles": all_articles}, f)

        return all_articles


class DataCollector:
    def __init__(self):
        self.eia = EIACollector() if settings.EIA_API_KEY else None
        self.fred = FREDCollector() if settings.FRED_API_KEY else None
        self.news = NewsCollector()
        self.gnews = GNewsCollector()
        self.opinet = OpinetCollector()
        self.db = Database()

    def _forward_fill_prices(self, df: pd.DataFrame) -> pd.DataFrame:
        """값이 없거나 0인 경우 전일 데이터를 사용하여 보간 (Forward-fill)"""
        if df.empty:
            return df
        
        # 0은 유효한 유가로 보기 어려우므로 결측치로 취급하여 ffill이 작동하도록 함
        for col in ['dubai', 'wti', 'brent']:
            if col in df.columns:
                df[col] = df[col].replace(0, None)
        
        # 날짜순 정렬 후 결측치 채움
        df = df.sort_values('date')
        df[['dubai', 'wti', 'brent']] = df[['dubai', 'wti', 'brent']].ffill()
        return df

    async def collect_prices(self, start_date: str, end_date: str) -> PriceHistory:
        df = await self.opinet.get_crude_prices(start_date, end_date)
        prices = [OilPrice(**row) for _, row in df.iterrows()]

        # SQLite에 저장
        if prices:
            await self.db.upsert_oil_prices([{"date": p.date, "dubai": p.dubai, "wti": p.wti, "brent": p.brent} for p in prices])

        return PriceHistory(prices=prices, source="opinet", last_updated=datetime.now().isoformat())

    async def collect_inventory(self, start_date: str, end_date: str) -> pd.DataFrame:
        """재고 데이터 수집 + DB 저장"""
        if not self.eia:
            return pd.DataFrame(columns=['date', 'inventory_mbbl'])
        df = await self.eia.get_crude_inventory(start_date, end_date)

        if not df.empty:
            await self.db.upsert_oil_inventory(df.to_dict('records'))

        return df

    async def collect_production(self, start_date: str, end_date: str) -> pd.DataFrame:
        """생산량 데이터 수집 + DB 저장"""
        if not self.eia:
            return pd.DataFrame(columns=['date', 'production_mbbl_d'])
        df = await self.eia.get_production(start_date, end_date)

        if not df.empty:
            await self.db.upsert_oil_production(df.to_dict('records'))

        return df

    async def collect_macro_data(self, start_date: str, end_date: str) -> MacroHistory:
        if not self.fred:
            return MacroHistory(indicators=[], source="fred", last_updated=datetime.now().isoformat())
        df = await self.fred.get_macro_indicators(start_date, end_date)
        indicators = [MacroIndicator(**row) for _, row in df.iterrows()]

        # SQLite에 저장
        if indicators:
            await self.db.upsert_macro_indicators(
                [{"date": i.date, "fed_rate": i.fed_rate, "dollar_index": i.dollar_index} for i in indicators]
            )

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
        elif source == "gnews":
            content = article.get('content') or article.get('description') or ''
            pub_date = article.get('publishedAt', '')
            return {
                "id": sha256(article['url'].encode()).hexdigest(),
                "title": article['title'], "description": article.get('description'),
                "source": article.get('source', {}).get('name'), "url": article['url'],
                "published_at": pub_date, "content_snippet": content[:200] if content else None,
                "data_source": "gnews"
            }
        return {}

    async def collect_news(self) -> List[Dict[str, Any]]:
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        
        newsapi_task = self.news.get_latest_news()
        gdelt_task = self.news.get_gdelt_events(yesterday, today)
        gnews_task = self.gnews.get_latest_news()
        
        newsapi_articles, gdelt_articles, gnews_articles = await asyncio.gather(
            newsapi_task, gdelt_task, gnews_task
        )
        
        all_articles = []
        seen_urls = set()

        for article in (newsapi_articles or []):
            if article.get('url') and article['url'] not in seen_urls:
                normalized = self._normalize_article(article, "newsapi")
                if normalized:
                    all_articles.append(normalized)
                    seen_urls.add(article['url'])
        
        for article in (gdelt_articles or []):
            if article.get('url') and article['url'] not in seen_urls:
                normalized = self._normalize_article(article, "gdelt")
                if normalized:
                    all_articles.append(normalized)
                    seen_urls.add(article['url'])

        for article in (gnews_articles or []):
            if article.get('url') and article['url'] not in seen_urls:
                normalized = self._normalize_article(article, "gnews")
                if normalized:
                    all_articles.append(normalized)
                    seen_urls.add(article['url'])

        # SQLite에 저장
        if all_articles:
            await self.db.upsert_news_articles(all_articles)
        
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
        """
        분석용 유가 DataFrame 반환.
        SQLite에 충분한 데이터가 있으면 API 호출 없이 DB에서 로드.
        """
        # 1차: SQLite에서 조회 시도
        end_date = date.today()
        start_date = end_date - timedelta(days=100)
        db_rows = await self.db.get_oil_prices(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            limit=500,
        )
        if len(db_rows) >= 30:
            logger.info(f"[DataCollector] Using {len(db_rows)} price records from SQLite (skipping API)")
            df = pd.DataFrame(db_rows)
            df = df[['date', 'dubai', 'wti', 'brent']].sort_values('date')
            return self._forward_fill_prices(df)

        # 2차: API에서 수집
        price_history = await self.collect_prices(start_date.isoformat(), end_date.isoformat())
        if not price_history or not price_history.prices:
            return pd.DataFrame()
        
        df = pd.DataFrame([p.model_dump() for p in price_history.prices])
        return self._forward_fill_prices(df)

    async def collect_macro_df_for_features(self) -> pd.DataFrame:
        """
        분석용 거시경제 DataFrame 반환.
        SQLite에 충분한 데이터가 있으면 API 호출 없이 DB에서 로드.
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=100)
        db_rows = await self.db.get_macro_indicators(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            limit=500,
        )
        if len(db_rows) >= 10:
            logger.info(f"[DataCollector] Using {len(db_rows)} macro records from SQLite (skipping API)")
            df = pd.DataFrame(db_rows)
            df = df[['date', 'fed_rate', 'dollar_index']].sort_values('date')
            return df

        macro_history = await self.collect_macro_data(start_date.isoformat(), end_date.isoformat())
        if not macro_history or not macro_history.indicators:
            return pd.DataFrame()
        return pd.DataFrame([i.model_dump() for i in macro_history.indicators])
