import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, date
import pandas as pd
import httpx
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

class OpinetCollector:
    """
    한국석유공사 오피넷(Opinet)에서 국제유가(Dubai, Brent, WTI)를 스크래핑하는 수집기.
    """
    
    BASE_URL = "https://www.opinet.co.kr/glopcoilSelect.do"

    def __init__(self):
        pass
        
    async def get_crude_prices(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        주어진 기간의 국제 유가(Dubai, Brent, WTI) 데이터를 조회합니다.
        
        Args:
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
            
        Returns:
            pd.DataFrame: ['date', 'dubai', 'brent', 'wti'] 컬럼을 가진 데이터프레임
        """
        # Parse dates
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            logger.error(f"Invalid date format: {start_date} ~ {end_date}")
            return pd.DataFrame(columns=['date', 'dubai', 'brent', 'wti'])

        # Prepare payload
        payload = {
            "TERM": "D",
            "TERM_D": "D",
            "STA_Y": str(start_dt.year),
            "STA_M": f"{start_dt.month:02d}",
            "STA_D": f"{start_dt.day:02d}",
            "END_Y": str(end_dt.year),
            "END_M": f"{end_dt.month:02d}",
            "END_D": f"{end_dt.day:02d}",
            "OILSRTCD1": "001",
            "OILSRTCD2": "002",
            "OILSRTCD3": "003",
            "OILSRTCD": ["001", "002", "003"],
            "SEL_DIV": "div_dar", # Dollar option in UI
        }

        # We don't use _fetch_api directly because Opinet needs POST form-data, not JSON or query params, and returns HTML.
        try:
            # Add backoff logic using the base class method if we want, or just httpx.
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.BASE_URL,
                    data=payload,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                        "Content-Type": "application/x-www-form-urlencoded"
                    }
                )
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Opinet scraping failed: {str(e)}")
            return pd.DataFrame(columns=['date', 'dubai', 'brent', 'wti'])

        html = response.text
        soup = BeautifulSoup(html, "lxml")
        
        # In Opinet, tbody1 is KRW, tbody2 is USD. We want USD.
        tbody2 = soup.find("tbody", id="tbody2")
        if not tbody2:
            logger.warning("No USD table (tbody2) found in Opinet response.")
            return pd.DataFrame(columns=['date', 'dubai', 'brent', 'wti'])
            
        rows = tbody2.find_all("tr")
        data_records = []
        
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 4:
                # 0: date, 1: dubai, 2: brent, 3: wti
                raw_date = cols[0].text.strip()
                dubai_val = cols[1].text.strip()
                brent_val = cols[2].text.strip()
                wti_val = cols[3].text.strip()
                
                # Parse '26년04월23일' -> '2026-04-23'
                match = re.match(r"(\d+)년(\d+)월(\d+)일", raw_date)
                if match:
                    y, m, d = match.groups()
                    y = "20" + y if len(y) == 2 else y
                    formatted_date = f"{y}-{m}-{d}"
                    
                    def safe_float(v):
                        v = v.replace(',', '')
                        return float(v) if v and v != '-' else None
                        
                    data_records.append({
                        'date': formatted_date,
                        'dubai': safe_float(dubai_val),
                        'brent': safe_float(brent_val),
                        'wti': safe_float(wti_val)
                    })
                    
        df = pd.DataFrame(data_records)
        if df.empty:
            df = pd.DataFrame(columns=['date', 'dubai', 'brent', 'wti'])
            return df
            
        # Clean up any None values using ffill or dropna based on requirements.
        # But we'll just return raw dataframe for the database to handle.
        return df
