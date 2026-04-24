# Step 2: EIA API 데이터 수집기 구현

## 목표
미국 에너지정보청(EIA) API v2를 통해 WTI/Brent 유가, 미국 원유 재고, 생산량 데이터를 수집하는 서비스를 구현한다.

## 배경
- EIA API v2 베이스 URL: `https://api.eia.gov/v2/`
- 인증: 쿼리 파라미터 `api_key=<KEY>`
- 문서: https://www.eia.gov/opendata/documentation.php

## 작업

### 1. EIA 데이터 수집 서비스
`backend/app/services/data_collector.py`에 `EIACollector` 클래스를 구현한다:

```python
class EIACollector:
    """EIA API v2 데이터 수집기"""

    async def get_crude_prices(self, start_date: str, end_date: str) -> pd.DataFrame:
        """WTI, Brent 일별 현물 가격 조회"""
        # EIA series: PET.RWTC.D (WTI), PET.RBRTE.D (Brent)
        ...

    async def get_crude_inventory(self, start_date: str, end_date: str) -> pd.DataFrame:
        """미국 원유 재고 주간 데이터 조회"""
        # EIA series: PET.WCESTUS1.W
        ...

    async def get_production(self, start_date: str, end_date: str) -> pd.DataFrame:
        """미국 원유 생산량 데이터 조회"""
        ...
```

### 2. 데이터 캐싱
- 같은 날 같은 쿼리를 반복하지 않도록 JSON 파일 캐시 구현
- 캐시 경로: `backend/data/raw/eia/YYYY-MM-DD_<series_id>.json`
- 캐시가 있으면 API 호출 대신 캐시 반환
- 캐시 만료: 24시간

### 3. Pydantic 스키마
`backend/app/schemas/price.py`에 응답 스키마를 정의한다:

```python
class OilPrice(BaseModel):
    date: str           # YYYY-MM-DD
    wti: float | None   # WTI 현물가 (USD/bbl)
    brent: float | None # Brent 현물가 (USD/bbl)

class PriceHistory(BaseModel):
    prices: list[OilPrice]
    source: str         # "eia"
    last_updated: str
```

### 4. 테스트
`backend/tests/test_eia_collector.py`에 테스트를 작성한다:
- API 응답 mocking (httpx)
- 캐시 동작 테스트
- 날짜 범위 파싱 테스트

## AC (Acceptance Criteria)
1. `EIACollector`가 WTI/Brent 일별 가격을 DataFrame으로 반환한다
2. 재고 및 생산량 데이터를 조회할 수 있다
3. 동일 쿼리 재요청 시 캐시에서 응답한다
4. API 키가 없을 때 적절한 에러 메시지를 반환한다
5. `pytest backend/tests/test_eia_collector.py` 가 통과한다
