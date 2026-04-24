# Step 3: FRED API 데이터 수집기 구현

## 목표
연방준비은행 경제 데이터(FRED) API를 통해 유가에 영향을 미치는 거시경제 지표를 수집하는 서비스를 구현한다.

## 배경
- FRED API 베이스 URL: `https://api.stlouisfed.org/fred/`
- 인증: 쿼리 파라미터 `api_key=<KEY>`
- 주요 시리즈:
  - `FEDFUNDS`: 연방기금금리 (월별)
  - `DTWEXBGS`: 미국 달러 광의 가중 인덱스 (일별)
  - `CPIAUCSL`: 소비자물가지수 (월별)
  - `INDPRO`: 산업생산지수 (월별)
  - `T10Y2Y`: 10년-2년 국채 스프레드 (일별, 경기 침체 지표)
  - `DCOILWTICO`: WTI 원유 가격 (FRED 자체 제공, EIA 교차검증용)

## 작업

### 1. FRED 데이터 수집 서비스
`backend/app/services/data_collector.py`에 `FREDCollector` 클래스를 추가한다:

```python
class FREDCollector:
    """FRED API 데이터 수집기"""

    MACRO_SERIES = {
        "fed_rate": "FEDFUNDS",
        "dollar_index": "DTWEXBGS",
        "cpi": "CPIAUCSL",
        "industrial_prod": "INDPRO",
        "yield_spread": "T10Y2Y",
    }

    async def get_series(self, series_id: str, start_date: str, end_date: str) -> pd.DataFrame:
        """단일 FRED 시리즈 조회"""
        ...

    async def get_macro_indicators(self, start_date: str, end_date: str) -> pd.DataFrame:
        """모든 거시경제 지표를 병합하여 반환 (날짜 기준 outer join)"""
        ...
```

### 2. 데이터 캐싱
- EIA 수집기와 동일한 캐시 패턴 사용
- 캐시 경로: `backend/data/raw/fred/YYYY-MM-DD_<series_id>.json`

### 3. Pydantic 스키마
`backend/app/schemas/price.py`에 추가:

```python
class MacroIndicator(BaseModel):
    date: str
    fed_rate: float | None
    dollar_index: float | None
    cpi: float | None
    industrial_prod: float | None
    yield_spread: float | None

class MacroHistory(BaseModel):
    indicators: list[MacroIndicator]
    source: str  # "fred"
    last_updated: str
```

### 4. 통합 수집기
`backend/app/services/data_collector.py`에 `DataCollector` 파사드 클래스를 만든다:

```python
class DataCollector:
    """모든 데이터 소스를 통합하는 파사드"""

    def __init__(self):
        self.eia = EIACollector()
        self.fred = FREDCollector()

    async def collect_all(self, start_date: str, end_date: str) -> dict:
        """모든 소스에서 데이터를 병렬 수집"""
        ...
```

### 5. 테스트
`backend/tests/test_fred_collector.py`에 테스트를 작성한다:
- FRED API 응답 mocking
- 여러 시리즈 병합 로직 테스트
- 날짜 주기가 다른 시리즈(일별 vs 월별)의 정렬 테스트

## AC (Acceptance Criteria)
1. `FREDCollector`가 5개 거시경제 지표를 DataFrame으로 반환한다
2. 일별/월별 시리즈가 날짜 기준으로 올바르게 병합된다
3. `DataCollector.collect_all()`이 EIA + FRED 데이터를 병렬로 수집한다
4. 캐시가 정상 동작한다
5. `pytest backend/tests/test_fred_collector.py` 가 통과한다
