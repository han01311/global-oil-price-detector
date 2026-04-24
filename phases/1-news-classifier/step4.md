# Step 4: 유사 사례 검색 API 구현

## 목표
프론트엔드에서 뉴스 분류 결과와 유사 과거 사례를 조회할 수 있는 API 엔드포인트를 구현한다.

## 작업

### 1. 뉴스 분류 API
`backend/app/api/news.py`에 엔드포인트를 추가한다:

```python
@router.post("/classify")
async def classify_news(
    articles: list[NewsArticle] = None,
    fetch_latest: bool = Query(default=True),
) -> list[ClassifiedArticle]:
    """뉴스 기사를 분류하고 영향도를 평가한다
    - articles 제공 시: 해당 기사를 분류
    - fetch_latest=True 시: 최신 뉴스를 수집하여 분류
    """
    ...

@router.get("/classified")
async def get_classified_news(
    category: str = Query(default=None),
    min_score: int = Query(default=None, ge=-5, le=5),
    limit: int = Query(default=20, le=50),
) -> list[ClassifiedArticle]:
    """분류된 뉴스 조회 (캐시된 결과)"""
    ...
```

### 2. 유사 사례 검색 API
`backend/app/api/news.py`에 추가:

```python
@router.get("/similar")
async def search_similar_events(
    query: str = Query(..., description="검색 쿼리 (뉴스 제목 또는 키워드)"),
    category: str = Query(default=None),
    limit: int = Query(default=5, le=20),
) -> list[SimilarEvent]:
    """유사 과거 사례 검색"""
    ...

@router.get("/factors/summary")
async def get_factor_summary() -> FactorSummary:
    """현재 6대 요인별 종합 스코어 반환"""
    # 최근 24시간 분류된 기사의 카테고리별 평균 Impact Score
    ...
```

### 3. 응답 스키마
`backend/app/schemas/news.py`에 추가:

```python
class SimilarEvent(BaseModel):
    title: str
    summary: str
    category: str
    impact_score: int
    date: str
    wti_change_1d: float
    wti_change_7d: float
    wti_change_30d: float
    similarity: float          # 유사도 (0~1)

class FactorScore(BaseModel):
    category: str
    avg_score: float           # 평균 Impact Score
    article_count: int         # 기사 수
    trend: str                 # "bullish" | "bearish" | "neutral"

class FactorSummary(BaseModel):
    factors: list[FactorScore]
    overall_sentiment: float   # 종합 감성 (-5 ~ +5)
    updated_at: str
```

### 4. 테스트
`backend/tests/test_api_news.py`:
- 뉴스 분류 API 테스트
- 유사 사례 검색 API 테스트
- 요인 요약 API 테스트
- 파라미터 검증 테스트

## AC (Acceptance Criteria)
1. `POST /api/news/classify`가 기사를 분류하여 반환한다
2. `GET /api/news/similar?query=...`가 유사 과거 사례를 반환한다
3. `GET /api/news/factors/summary`가 6대 요인 종합 스코어를 반환한다
4. 카테고리 필터링과 스코어 필터링이 동작한다
5. `pytest backend/tests/test_api_news.py` 가 통과한다
