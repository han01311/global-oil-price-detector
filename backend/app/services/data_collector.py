"""
외부 API로부터 데이터를 수집하는 서비스
EIA (U.S. Energy Information Administration) 데이터 수집기
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd
from app.core.config import settings


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
