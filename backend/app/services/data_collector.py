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
        
        merged_df = merged_df.sort_values('date')
        merged_df = merged_df[(merged_df['date'] >= start_date) & (merged_df['date'] <= end_date)]
        
        # SQLite 저장을 위해 NaN을 None으로 변환
        merged_df = merged_df.where(pd.notnull(merged_df), None)
        return merged_df


class NYTCollector(BaseCollector):
    """NYT Article Search API 수집기"""
    def __init__(self, api_key: str | None = None):
        api_key = api_key or settings.NYT_API_KEY
        super().__init__(api_key, "https://api.nytimes.com/svc/search/v2")

    async def get_latest_news(self) -> List[Dict[str, Any]]:
        if not self.api_key:
            return []
        
        params = {
            "q": '("crude oil" OR "oil price" OR "OPEC")',
            "sort": "newest",
            "api-key": self.api_key
        }
        
        try:
            data = await self._fetch_api("/articlesearch.json", params, "nyt_news", rate_limit_source="nyt")
            return data.get("response", {}).get("docs", [])
        except Exception as e:
            logger.error(f"NYT fetch failed: {e}")
            return []

class GuardianCollector(BaseCollector):
    """The Guardian Open Platform API 수집기"""
    def __init__(self, api_key: str | None = None):
        api_key = api_key or settings.GUARDIAN_API_KEY
        super().__init__(api_key, "https://content.guardianapis.com")

    async def get_latest_news(self) -> List[Dict[str, Any]]:
        if not self.api_key:
            return []
        
        params = {
            "q": '"crude oil" OR "oil price" OR OPEC',
            "order-by": "newest",
            "show-fields": "trailText",
            "api-key": self.api_key
        }
        
        try:
            data = await self._fetch_api("/search", params, "guardian_news", rate_limit_source="guardian")
            return data.get("response", {}).get("results", [])
        except Exception as e:
            logger.error(f"Guardian fetch failed: {e}")
            return []


class DataCollector:
    def __init__(self):
        self.eia = EIACollector() if settings.EIA_API_KEY else None
        self.fred = FREDCollector() if settings.FRED_API_KEY else None
        self.nyt = NYTCollector()
        self.guardian = GuardianCollector()
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
        if source == "nyt":
            title = article.get('headline', {}).get('main', '')
            description = article.get('abstract', '') or article.get('snippet', '')
            pub_date = article.get('pub_date', datetime.now().isoformat())
            link = article.get('web_url', '')

            return {
                "id": sha256(link.encode()).hexdigest(),
                "title": title, 
                "description": description,
                "source": "New York Times", 
                "url": link,
                "published_at": pub_date, 
                "content_snippet": description[:200] if description else None,
                "data_source": "nyt"
            }
            
        elif source == "guardian":
            title = article.get('webTitle', '')
            description = article.get('fields', {}).get('trailText', '')
            
            import html
            import re
            def clean_html(raw_html):
                cleanr = re.compile('<.*?>')
                cleantext = re.sub(cleanr, '', raw_html)
                return html.unescape(cleantext)
                
            description = clean_html(description)
            
            pub_date = article.get('webPublicationDate', datetime.now().isoformat())
            link = article.get('webUrl', '')

            return {
                "id": sha256(link.encode()).hexdigest(),
                "title": title, 
                "description": description,
                "source": "The Guardian", 
                "url": link,
                "published_at": pub_date, 
                "content_snippet": description[:200] if description else None,
                "data_source": "guardian"
            }
        return {}

    async def collect_news(self) -> List[Dict[str, Any]]:
        nyt_task = self.nyt.get_latest_news()
        guardian_task = self.guardian.get_latest_news()
        
        nyt_articles, guardian_articles = await asyncio.gather(nyt_task, guardian_task)
        
        all_articles = []
        seen_urls = set()

        for article in (nyt_articles or []):
            link = article.get('web_url')
            if link and link not in seen_urls:
                normalized = self._normalize_article(article, "nyt")
                if normalized:
                    all_articles.append(normalized)
                    seen_urls.add(link)
                    
        for article in (guardian_articles or []):
            link = article.get('webUrl')
            if link and link not in seen_urls:
                normalized = self._normalize_article(article, "guardian")
                if normalized:
                    all_articles.append(normalized)
                    seen_urls.add(link)

        # SQLite에 저장
        if all_articles:
            await self.db.upsert_news_articles(all_articles)
        
        # 새롭게 DB에 인서트된 기사만 필터링하여 반환
        new_articles = [a for a in all_articles if a.get('_is_new')]
        return new_articles

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
            df[['fed_rate', 'dollar_index']] = df[['fed_rate', 'dollar_index']].ffill().bfill()
            return df

        macro_history = await self.collect_macro_data(start_date.isoformat(), end_date.isoformat())
        if not macro_history or not macro_history.indicators:
            return pd.DataFrame(columns=['date', 'fed_rate', 'dollar_index'])

        df = pd.DataFrame([{"date": i.date, "fed_rate": i.fed_rate, "dollar_index": i.dollar_index} for i in macro_history.indicators])
        df = df.sort_values('date')
        df[['fed_rate', 'dollar_index']] = df[['fed_rate', 'dollar_index']].ffill().bfill()
        return df
