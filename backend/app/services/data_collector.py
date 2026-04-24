"""
외부 API로부터 데이터를 수집하는 서비스
EIA (U.S. Energy Information Administration) 데이터 수집기
FRED (Federal Reserve Economic Data) 데이터 수집기
News API / GDELT 뉴스 데이터 수집기
"""
import asyncio
import json
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from functools import reduce

import httpx
import pandas as pd
from app.core.config import settings

logger = logging.getLogger(__name__)


class EIACollector:
    """EIA API v2 데이터 수집기"""

    BASE_URL = "https://api.eia.gov/v2/"

    def __init__(self, api_key: str | None = settings.EIA_API_KEY):
        if not api_key:
            raise ValueError("EIA_API_KEY is required for EIACollector.")
        self.api_key = api_key
        self.cache_dir = Path(settings.DATA_CACHE_DIR) / "raw" / "eia"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def _fetch_series(self, path: str, series_id: str, start_date: str, end_date: str) -> list[dict]:
        """단일 시리즈 데이터를 API 또는 캐시에서 가져옵니다."""
        today = datetime.now().strftime('%Y-%m-%d')
        cache_file = self.cache_dir / f"{today}_{series_id}.json"

        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('response', {}).get('data', [])

        params = {
            "api_key": self.api_key,
            "data[0]": "value",
            "facets[seriesId][]": series_id,
            "start": start_date,
            "end": end_date,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "offset": 0,
            "length": 5000,
        }

        if '.W' in series_id.upper():
            params['frequency'] = 'weekly'
        else:
            params['frequency'] = 'daily'

        url = f"{self.BASE_URL}{path}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f)

            return data.get('response', {}).get('data', [])

    def _to_dataframe(self, data: list[dict], value_col_name: str) -> pd.DataFrame:
        """EIA API 응답을 DataFrame으로 변환합니다."""
        if not data:
            return pd.DataFrame(columns=['date', value_col_name])
        df = pd.DataFrame(data)
        df = df.rename(columns={'period': 'date', 'value': value_col_name})
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        return df[['date', value_col_name]]

    async def get_crude_prices(self, start_date: str, end_date: str) -> pd.DataFrame:
        """WTI, Brent 일별 현물 가격 조회"""
        path = "petroleum/pri/spt/data/"
        wti_series = "PET.RWTC.D"
        brent_series = "PET.RBRTE.D"

        wti_task = self._fetch_series(path, wti_series, start_date, end_date)
        brent_task = self._fetch_series(path, brent_series, start_date, end_date)

        wti_data, brent_data = await asyncio.gather(wti_task, brent_task)

        df_wti = self._to_dataframe(wti_data, 'wti')
        df_brent = self._to_dataframe(brent_data, 'brent')

        if df_wti.empty and df_brent.empty:
            return pd.DataFrame(columns=['date', 'wti', 'brent'])
        if df_wti.empty:
            return df_brent.assign(wti=None)
        if df_brent.empty:
            return df_wti.assign(brent=None)

        df = pd.merge(df_wti, df_brent, on='date', how='outer')
        df = df.sort_values(by='date').reset_index(drop=True)
        return df

    async def get_crude_inventory(self, start_date: str, end_date: str) -> pd.DataFrame:
        """미국 원유 재고 주간 데이터 조회 (단위: 천 배럴)"""
        path = "petroleum/stoc/wstk/data/"
        series_id = "PET.WCESTUS1.W"
        data = await self._fetch_series(path, series_id, start_date, end_date)
        df = self._to_dataframe(data, 'inventory_mbbl')
        return df

    async def get_production(self, start_date: str, end_date: str) -> pd.DataFrame:
        """미국 원유 생산량 데이터 조회 (단위: 일일 천 배럴)"""
        path = "petroleum/crd/crpdn/data/"
        series_id = "PET.WCRFPUS2.W"
        data = await self._fetch_series(path, series_id, start_date, end_date)
        df = self._to_dataframe(data, 'production_mbbl_d')
        return df


class FREDCollector:
    """FRED API 데이터 수집기"""

    BASE_URL = "https://api.stlouisfed.org/fred/"

    MACRO_SERIES = {
        "fed_rate": "FEDFUNDS",
        "dollar_index": "DTWEXBGS",
        "cpi": "CPIAUCSL",
        "industrial_prod": "INDPRO",
        "yield_spread": "T10Y2Y",
    }

    def __init__(self, api_key: str | None = settings.FRED_API_KEY):
        if not api_key:
            raise ValueError("FRED_API_KEY is required for FREDCollector.")
        self.api_key = api_key
        self.cache_dir = Path(settings.DATA_CACHE_DIR) / "raw" / "fred"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def _fetch_series(self, series_id: str, start_date: str, end_date: str) -> list[dict]:
        """단일 FRED 시리즈 데이터를 API 또는 캐시에서 가져옵니다."""
        today = datetime.now().strftime('%Y-%m-%d')
        cache_file = self.cache_dir / f"{today}_{series_id}.json"

        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f).get("observations", [])

        params = {
            "api_key": self.api_key,
            "series_id": series_id,
            "observation_start": start_date,
            "observation_end": end_date,
            "file_type": "json",
        }
        url = f"{self.BASE_URL}series/observations"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f)

            return data.get("observations", [])

    def _to_dataframe(self, data: list[dict], value_col_name: str) -> pd.DataFrame:
        """FRED API 응답을 DataFrame으로 변환합니다."""
        if not data:
            return pd.DataFrame(columns=['date', value_col_name])
        df = pd.DataFrame(data)
        df = df.rename(columns={'value': value_col_name})
        df = df[['date', value_col_name]]
        # FRED는 누락 데이터를 '.'으로 표시하므로 숫자로 변환하고 에러는 NaN으로 처리
        df[value_col_name] = pd.to_numeric(df[value_col_name], errors='coerce')
        df = df.dropna(subset=[value_col_name])
        return df

    async def get_series(self, series_id: str, name: str, start_date: str, end_date: str) -> pd.DataFrame:
        """단일 FRED 시리즈 조회"""
        data = await self._fetch_series(series_id, start_date, end_date)
        return self._to_dataframe(data, name)

    async def get_macro_indicators(self, start_date: str, end_date: str) -> pd.DataFrame:
        """모든 거시경제 지표를 병합하여 반환 (날짜 기준 outer join)"""
        tasks = []
        for name, series_id in self.MACRO_SERIES.items():
            tasks.append(self.get_series(series_id, name, start_date, end_date))

        dataframes = await asyncio.gather(*tasks)

        # 빈 데이터프레임 제거
        dataframes = [df for df in dataframes if not df.empty]

        if not dataframes:
            return pd.DataFrame()

        # 모든 데이터프레임을 날짜 기준으로 병합
        merged_df = reduce(lambda left, right: pd.merge(left, right, on='date', how='outer'), dataframes)
        merged_df = merged_df.sort_values(by='date').reset_index(drop=True)

        # 월별 데이터를 일별 데이터에 맞게 forward-fill
        merged_df = merged_df.ffill()
        return merged_df


class NewsCollector:
    """뉴스 데이터 수집기"""

    NEWSAPI_URL = "https://newsapi.org/v2/everything"
    GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    # 유가 관련 키워드 (영문)
    OIL_KEYWORDS = [
        "crude oil", "oil prices", "WTI", "Brent",
        "OPEC", "oil production", "oil demand",
        "petroleum", "oil supply", "energy crisis",
        "oil sanctions", "shale oil", "oil reserves",
    ]

    def __init__(self):
        self.cache_dir = Path(settings.DATA_CACHE_DIR) / "raw" / "news"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def get_latest_news(self, max_articles: int = 50) -> list[dict]:
        """NewsAPI에서 최신 유가 관련 기사 수집"""
        if not settings.NEWS_API_KEY:
            logger.warning("NEWS_API_KEY is not set. Skipping NewsAPI fetch.")
            return []

        today = datetime.now().strftime('%Y-%m-%d')
        cache_file = self.cache_dir / f"{today}_newsapi.json"

        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        query = " OR ".join(f'"{k}"' for k in self.OIL_KEYWORDS)
        params = {
            "q": query,
            "apiKey": settings.NEWS_API_KEY,
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": max_articles,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(self.NEWSAPI_URL, params=params)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"NewsAPI request failed: {e}")
                return []

        articles = []
        for article in data.get("articles", []):
            if not article.get('url'):
                continue
            articles.append({
                "id": hashlib.sha256(article['url'].encode()).hexdigest(),
                "title": article.get('title', ''),
                "description": article.get('description'),
                "source": article.get('source', {}).get('name'),
                "url": article['url'],
                "published_at": article.get('publishedAt', ''),
                "content_snippet": article.get('content'),
                "data_source": "newsapi",
            })

        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(articles, f)

        return articles

    async def get_gdelt_events(self, start_date: str, end_date: str) -> list[dict]:
        """GDELT에서 에너지 관련 이벤트 수집"""
        today = datetime.now().strftime('%Y-%m-%d')
        cache_file = self.cache_dir / f"{today}_gdelt.json"

        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        # GDELT date format is YYYYMMDDHHMMSS
        start_dt = f"{start_date.replace('-', '')}000000"
        end_dt = f"{end_date.replace('-', '')}235959"

        query = "(oil OR crude OR OPEC OR petroleum) (sourcelang:eng)"
        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "startdatetime": start_dt,
            "enddatetime": end_dt,
            "maxrecords": 100,  # GDELT has a limit
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(self.GDELT_URL, params=params)
                response.raise_for_status()
                data = response.json()
            except (httpx.HTTPStatusError, json.JSONDecodeError) as e:
                logger.error(f"GDELT request failed: {e}")
                return []

        articles = []
        for article in data.get("articles", []):
            if not article.get('url'):
                continue

            # GDELT seendate format: 20231101143000
            published_str = article.get('seendate', '')
            try:
                published_dt = datetime.strptime(published_str, '%Y%m%d%H%M%S')
                published_iso = published_dt.isoformat() + "Z"
            except ValueError:
                published_iso = ''

            articles.append({
                "id": hashlib.sha256(article['url'].encode()).hexdigest(),
                "title": article.get('title', ''),
                "description": article.get('socialimage'),  # GDELT doesn't provide a good description
                "source": article.get('domain'),
                "url": article['url'],
                "published_at": published_iso,
                "content_snippet": None,  # Not available
                "data_source": "gdelt",
            })

        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(articles, f)

        return articles


class DataCollector:
    """모든 데이터 소스를 통합하는 파사드"""

    def __init__(self):
        self.eia = EIACollector()
        self.fred = FREDCollector()
        self.news = NewsCollector()

    async def collect_all(self, start_date: str, end_date: str) -> dict[str, pd.DataFrame]:
        """모든 소스에서 데이터를 병렬 수집"""
        eia_prices_task = self.eia.get_crude_prices(start_date, end_date)
        eia_inventory_task = self.eia.get_crude_inventory(start_date, end_date)
        eia_production_task = self.eia.get_production(start_date, end_date)
        fred_macro_task = self.fred.get_macro_indicators(start_date, end_date)

        results = await asyncio.gather(
            eia_prices_task,
            eia_inventory_task,
            eia_production_task,
            fred_macro_task
        )

        return {
            "eia_prices": results[0],
            "eia_inventory": results[1],
            "eia_production": results[2],
            "fred_macro": results[3],
        }

    async def collect_news(self, max_articles: int = 50) -> list[dict]:
        """뉴스 수집 (NewsAPI + GDELT 병합, 중복 제거)"""
        today = datetime.now()
        start_date = (today - timedelta(days=1)).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')

        newsapi_task = self.news.get_latest_news(max_articles)
        gdelt_task = self.news.get_gdelt_events(start_date, end_date)

        newsapi_articles, gdelt_articles = await asyncio.gather(newsapi_task, gdelt_task)

        all_articles = newsapi_articles + gdelt_articles

        # URL 기준으로 중복 제거
        unique_articles = {}
        for article in all_articles:
            if article['url'] not in unique_articles:
                unique_articles[article['url']] = article

        return list(unique_articles.values())
