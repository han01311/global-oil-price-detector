# Step 5: 추정 엔진 API 엔드포인트 구현

## 목표
프론트엔드에서 유가 추정 결과와 AI 브리핑을 조회할 수 있는 API 엔드포인트를 구현한다.

## 작업

### 1. 추정 API 라우트
`backend/app/api/forecast.py`를 구현한다:

```python
router = APIRouter(prefix="/api/forecast", tags=["forecast"])

@router.get("/estimate")
async def get_price_estimate() -> ForecastResult:
    """현재 유가 추정 결과 조회
    - XGBoost baseline + 뉴스 보정이 결합된 최종 추정
    - 7일/30일 예측 밴드 포함
    """
    ...

@router.get("/baseline")
async def get_baseline_only(
    horizon: str = Query(default="7d", regex="^(7d|30d)$"),
) -> dict:
    """XGBoost 베이스라인만 조회 (뉴스 보정 제외)"""
    ...

@router.get("/model-info")
async def get_model_info() -> dict:
    """모델 정보 조회 (학습 날짜, RMSE, 피처 중요도)"""
    ...
```

### 2. 브리핑 API 라우트
`backend/app/api/briefing.py`를 구현한다:

```python
router = APIRouter(prefix="/api/briefing", tags=["briefing"])

@router.get("/today")
async def get_today_briefing() -> Briefing:
    """오늘의 유가 브리핑 조회 (캐시 있으면 캐시 반환)"""
    ...

@router.get("/history")
async def get_briefing_history(
    days: int = Query(default=7, le=30),
) -> list[Briefing]:
    """과거 브리핑 이력 조회"""
    ...

@router.post("/generate")
async def generate_briefing() -> Briefing:
    """브리핑 강제 재생성 (캐시 무시)"""
    ...
```

### 3. main.py 라우터 등록
`backend/app/main.py`에 forecast, briefing 라우터를 등록한다.

### 4. 테스트
`backend/tests/test_api_forecast.py`:
- 추정 API 응답 형태 검증
- 모델 미학습 시 에러 처리
- 브리핑 캐시 동작 검증

## AC (Acceptance Criteria)
1. `GET /api/forecast/estimate`가 추정 유가 밴드를 반환한다
2. `GET /api/briefing/today`가 AI 브리핑을 반환한다
3. 모델이 학습되지 않았을 때 적절한 에러를 반환한다
4. `/docs`에서 모든 엔드포인트가 정상 표시된다
5. `pytest backend/tests/test_api_forecast.py` 가 통과한다
