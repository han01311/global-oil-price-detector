"""
외부 API로부터 데이터를 수집하는 모듈
- EIA (유가, 재고, 생산량)
- FRED (거시경제 지표)
- NewsAPI / GDELT (뉴스)
"""
import asyncio
import hashlib
import json
import httpx
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.config import settings
from app.schemas.price import PriceHistory, OilPrice, MacroHistory, MacroIndicator

# --- Base Collector ---

class BaseCollector:
    """데이터 수집기 기본 클래스"""
    BASE_URL = ""

    def __init__(self, source: str):
        self.source = source
        self.cache_dir = Path(settings.DATA_CACHE_DIR) / "raw" / self.source
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def _fetch_data(self, url: str, params: dict | None = None) -> dict:
        """HTTP GET 요청을 보내고 JSON 응답을 반환"""
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def _fetch_with_cache(self, cache_key: str, url: str, params: dict | None = None) -> dict:
        """캐시를 확인하고, 없으면 API를 호출하여 결과를 캐시에 저장"""
        today = datetime.now().strftime('%Y-%m-%d')
        cache_file = self.cache_dir / f"{today}_{cache_key}.json"

        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        data = await self._fetch_data(url, params)
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data

# --- EIA Collector ---

class EIACollector(BaseCollector):
    """EIA API v2 데이터 수집기"""
    BASE_URL = "https://api.eia.gov/v2"
    SERIES = {
        "wti": "PET.RWTC.D",
        "brent": "PET.RBRTE.D",
        "inventory": "PET.WCESTUS1.W", # Crude Oil Stocks, Excluding SPR
        "production": "PET.WCRFPUS2.W" # US Field Production of Crude Oil
    }

    def __init__(self, api_key: str | None = None):
        super().__init__("eia")
        self.api_key = api_key or settings.EIA_API_KEY
        if not self.api_key:
            raise ValueError("EIA_API_KEY is required for EIACollector")

    async def _get_series(self, series_id: str, start: str, end: str) -> list[dict]:
        """EIA API에서 특정 시리즈 데이터를 가져옴"""
        url = f"{self.BASE_URL}/{series_id}/data/"
        params = {
            "api_key": self.api_key,
            "frequency": "daily",
            "data[0]": "value",
            "facets[seriesId][]": series_id,
            "start": start,
            "end": end,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "offset": 0,
            "length": 5000
        }
        data = await self._fetch_with_cache(series_id, url, params=params)
        return data.get("response", {}).get("data", [])

    async def get_crude_prices(self, start_date: str, end_date: str) -> pd.DataFrame:
        """WTI와 Brent 유가 데이터를 가져와 병합"""
        wti_data, brent_data = await asyncio.gather(
            self._get_series(self.SERIES["wti"], start_date, end_date),
            self._get_series(self.SERIES["brent"], start_date, end_date)
        )
        
        wti_df = pd.DataFrame(wti_data)[['period', 'value']].rename(columns={'period': 'date', 'value': 'wti'}) if wti_data else pd.DataFrame(columns=['date', 'wti'])
        brent_df = pd.DataFrame(brent_data)[['period', 'value']].rename(columns={'period': 'date', 'value': 'brent'}) if brent_data else pd.DataFrame(columns=['date', 'brent'])
        
        if wti_df.empty and brent_df.empty:
            return pd.DataFrame(columns=['date', 'wti', 'brent'])
        if wti_df.empty:
            return brent_df
        if brent_df.empty:
            return wti_df

        price_df = pd.merge(wti_df, brent_df, on='date', how='outer').sort_values('date').reset_index(drop=True)
        return price_df

    async def get_crude_inventory(self, start_date: str, end_date: str) -> pd.DataFrame:
        data = await self._get_series(self.SERIES["inventory"], start_date, end_date)
        if not data:
            return pd.DataFrame(columns=['date', 'inventory_mbbl'])
        df = pd.DataFrame(data)[['period', 'value']].rename(columns={'period': 'date', 'value': 'inventory_mbbl'})
        return df

    async def get_production(self, start_date: str, end_date: str) -> pd.DataFrame:
        data = await self._get_series(self.SERIES["production"], start_date, end_date)
        if not data:
            return pd.DataFrame(columns=['date', 'production_mbbl_d'])
        df = pd.DataFrame(data)[['period', 'value']].rename(columns={'period': 'date', 'value': 'production_mbbl_d'})
        return df

# --- FRED Collector ---

class FREDCollector(BaseCollector):
    """FRED API 데이터 수집기"""
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
    MACRO_SERIES = {
        "fed_rate": "FEDFUNDS",
        "dollar_index": "DTWEXBGS",
        "cpi": "CPIAUCSL",
        "industrial_prod": "INDPRO",
        "yield_spread": "T10Y2Y" # 10-Year Treasury Constant Maturity Minus 2-Year
    }

    def __init__(self, api_key: str | None = None):
        super().__init__("fred")
        self.api_key = api_key or settings.FRED_API_KEY
        if not self.api_key:
            raise ValueError("FRED_API_KEY is required for FREDCollector")

    async def get_series(self, series_id: str, col_name: str, start_date: str, end_date: str) -> pd.DataFrame:
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start_date,
            "observation_end": end_date,
        }
        data = await self._fetch_with_cache(series_id, self.BASE_URL, params=params)
        observations = data.get("observations", [])
        
        if not observations:
            return pd.DataFrame(columns=['date', col_name])
            
        df = pd.DataFrame(observations)[['date', 'value']]
        df = df[df['value'] != "."] # Filter out non-data points
        df = df.rename(columns={'value': col_name})
        df[col_name] = pd.to_numeric(df[col_name])
        return df

    async def get_macro_indicators(self, start_date: str, end_date: str) -> pd.DataFrame:
        tasks = [self.get_series(series_id, name, start_date, end_date) for name, series_id in self.MACRO_SERIES.items()]
        results = await asyncio.gather(*tasks)
        
        date_range = pd.date_range(start=start_date, end=end_date, freq='D').to_frame(name='date', index=False)
        date_range['date'] = date_range['date'].dt.strftime('%Y-%m-%d')

        merged_df = date_range
        for df in results:
            if not df.empty:
                merged_df = pd.merge(merged_df, df, on='date', how='left')
        
        merged_df = merged_df.ffill().dropna(subset=list(self.MACRO_SERIES.keys()), how='all').reset_index(drop=True)
        return merged_df

# --- News Collector ---

class NewsCollector(BaseCollector):
    """뉴스 데이터 수집기 (NewsAPI, GDELT)"""
    NEWSAPI_URL = "https://newsapi.org/v2/everything"
    GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
    KEYWORDS = [
        '"crude oil"', 'OPEC', 'shale', '"oil prices"', '"energy market"',
        '"oil demand"', '"oil supply"', '"oil reserves"', 'geopolitics AND oil'
    ]

    def __init__(self):
        super().__init__("news")

    def _normalize_newsapi_article(self, article: dict) -> dict:
        return {
            "id": hashlib.sha256(article['url'].encode()).hexdigest(),
            "title": article.get('title'),
            "description": article.get('description'),
            "source": article.get('source', {}).get('name'),
            "url": article.get('url'),
            "published_at": article.get('publishedAt'),
            "content_snippet": article.get('content'),
            "data_source": "newsapi"
        }

    def _normalize_gdelt_article(self, article: dict) -> dict:
        return {
            "id": hashlib.sha256(article['url'].encode()).hexdigest(),
            "title": article.get('title'),
            "description": None,
            "source": article.get('domain'),
            "url": article.get('url'),
            "published_at": datetime.strptime(article['seendate'], '%Y%m%d%H%M%S').isoformat() + 'Z',
            "content_snippet": None,
            "data_source": "gdelt"
        }

    async def get_latest_news(self) -> list[dict]:
        """NewsAPI에서 최신 뉴스 가져오기"""
        if not settings.NEWS_API_KEY:
            return []
        
        query = " OR ".join(self.KEYWORDS)
        params = {
            "q": query,
            "apiKey": settings.NEWS_API_KEY,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 100
        }
        data = await self._fetch_with_cache("newsapi", self.NEWSAPI_URL, params=params)
        return [self._normalize_newsapi_article(a) for a in data.get('articles', [])]

    async def get_gdelt_events(self, start_date: str, end_date: str) -> list[dict]:
        """GDELT에서 이벤트/뉴스 가져오기"""
        query = " OR ".join(self.KEYWORDS)
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y%m%d%H%M%S")
        end_dt = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d%H%M%S")

        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "startdatetime": start_dt,
            "enddatetime": end_dt,
            "maxrecords": 250,
            "sort": "DateDesc"
        }
        data = await self._fetch_with_cache(f"gdelt_{start_date}_{end_date}", self.GDELT_URL, params=params)
        return [self._normalize_gdelt_article(a) for a in data.get('articles', [])]

    async def collect_all_news(self) -> list[dict]:
        """모든 뉴스 소스에서 데이터를 수집하고 중복 제거"""
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        newsapi_task = self.get_latest_news()
        gdelt_task = self.get_gdelt_events(yesterday, today)
        
        all_articles_nested = await asyncio.gather(newsapi_task, gdelt_task)
        all_articles = [item for sublist in all_articles_nested for item in sublist]
        
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            if article['url'] not in seen_urls:
                unique_articles.append(article)
                seen_urls.add(article['url'])
        
        return unique_articles

# --- Main Data Collector ---

class DataCollector:
    """모든 데이터 소스로부터 데이터를 수집하는 메인 클래스"""
    def __init__(self):
        try:
            self.eia = EIACollector()
        except ValueError:
            self.eia = None
        
        try:
            self.fred = FREDCollector()
        except ValueError:
            self.fred = None
            
        self.news = NewsCollector()

    async def collect_prices(self, start_date: str, end_date: str) -> PriceHistory:
        if not self.eia:
            return PriceHistory(prices=[], source="eia", last_updated=datetime.now(timezone.utc).isoformat())
        
        df = await self.eia.get_crude_prices(start_date, end_date)
        prices = [OilPrice(**row) for row in df.to_dict('records')]
        return PriceHistory(
            prices=prices,
            source="eia",
            last_updated=datetime.now(timezone.utc).isoformat()
        )

    async def collect_macro_data(self, start_date: str, end_date: str) -> MacroHistory:
        if not self.fred:
            return MacroHistory(indicators=[], source="fred", last_updated=datetime.now(timezone.utc).isoformat())

        df = await self.fred.get_macro_indicators(start_date, end_date)
        indicators = [MacroIndicator(**row) for row in df.to_dict('records')]
        return MacroHistory(
            indicators=indicators,
            source="fred",
            last_updated=datetime.now(timezone.utc).isoformat()
        )

    async def collect_news(self) -> list[dict]:
        return await self.news.collect_all_news()

    async def collect_all(self, start_date: str, end_date: str) -> dict:
        """모든 데이터 소스로부터 병렬로 데이터를 수집"""
        tasks = {
            "prices": self.collect_prices(start_date, end_date),
            "macro": self.collect_macro_data(start_date, end_date),
            "news": self.collect_news()
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        output = {}
        for i, key in enumerate(tasks.keys()):
            result = results[i]
            if isinstance(result, Exception):
                print(f"Error collecting data for '{key}': {result}")
                if key == "prices":
                    output[key] = PriceHistory(prices=[], source="eia", last_updated="")
                elif key == "macro":
                    output[key] = MacroHistory(indicators=[], source="fred", last_updated="")
                elif key == "news":
                    output[key] = []
            else:
                output[key] = result
        
        return output
