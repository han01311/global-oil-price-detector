# Step 5: 유가 데이터 API 엔드포인트 구현

## 목표
프론트엔드에서 사용할 유가 데이터 및 뉴스 데이터 REST API 엔드포인트를 구현한다.

## 작업

### 1. 유가 데이터 라우트
`backend/app/api/prices.py`를 구현한다:

```python
router = APIRouter(prefix="/api/prices", tags=["prices"])

@router.get("/history")
async def get_price_history(
    start_date: str = Query(..., description="시작일 YYYY-MM-DD"),
    end_date: str = Query(..., description="종료일 YYYY-MM-DD"),
) -> PriceHistory:
    """WTI/Brent 일별 유가 이력 조회"""
    ...

@router.get("/latest")
async def get_latest_prices() -> OilPrice:
    """최신 유가 조회"""
    ...

@router.get("/macro")
async def get_macro_indicators(
    start_date: str = Query(...),
    end_date: str = Query(...),
) -> MacroHistory:
    """거시경제 지표 조회"""
    ...
```

### 2. 뉴스 데이터 라우트
`backend/app/api/news.py`를 구현한다:

```python
router = APIRouter(prefix="/api/news", tags=["news"])

@router.get("/latest")
async def get_latest_news(
    limit: int = Query(default=20, le=50),
) -> NewsCollection:
    """최신 유가 관련 뉴스 조회"""
    ...
```

### 3. main.py에 라우터 등록
`backend/app/main.py`에 prices, news 라우터를 등록한다.

### 4. API 문서 확인
- `/docs` (Swagger UI)에서 모든 엔드포인트가 보이는지 확인
- 각 엔드포인트의 응답 스키마가 올바른지 확인

### 5. 테스트
`backend/tests/test_api_prices.py`에 API 통합 테스트를 작성한다:
- FastAPI TestClient 사용
- 각 엔드포인트의 응답 형태 검증
- 잘못된 날짜 형식 에러 처리 검증

## AC (Acceptance Criteria)
1. `GET /api/prices/history?start_date=2024-01-01&end_date=2024-12-31`이 유가 데이터를 반환한다
2. `GET /api/prices/latest`가 최신 유가를 반환한다
3. `GET /api/prices/macro`가 거시경제 지표를 반환한다
4. `GET /api/news/latest`가 뉴스 기사를 반환한다
5. `/docs`에서 모든 엔드포인트가 정상 표시된다
6. `pytest backend/tests/test_api_prices.py` 가 통과한다
