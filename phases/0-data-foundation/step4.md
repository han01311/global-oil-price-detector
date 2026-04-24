# Step 4: 뉴스 API 데이터 수집기 구현

## 목표
NewsAPI와 GDELT를 통해 유가 관련 글로벌 뉴스를 수집하는 서비스를 구현한다. 수집된 뉴스는 이후 AI 요인 분류기의 입력이 된다.

## 작업

### 1. NewsAPI 수집기
`backend/app/services/data_collector.py`에 `NewsCollector` 클래스를 추가한다:

```python
class NewsCollector:
    """뉴스 데이터 수집기"""

    # 유가 관련 키워드 (영문)
    OIL_KEYWORDS = [
        "crude oil", "oil prices", "WTI", "Brent",
        "OPEC", "oil production", "oil demand",
        "petroleum", "oil supply", "energy crisis",
        "oil sanctions", "shale oil", "oil reserves",
    ]

    async def get_latest_news(self, max_articles: int = 50) -> list[dict]:
        """NewsAPI에서 최신 유가 관련 기사 수집"""
        # GET https://newsapi.org/v2/everything
        # q= OR 조합 쿼리
        # sortBy=publishedAt
        # language=en
        ...

    async def get_gdelt_events(self, start_date: str, end_date: str) -> list[dict]:
        """GDELT에서 에너지 관련 이벤트 수집"""
        # GDELT DOC API: https://api.gdeltproject.org/api/v2/doc/doc
        # query: oil OR crude OR OPEC OR petroleum
        # mode: ArtList
        # format: json
        ...
```

### 2. 뉴스 스키마
`backend/app/schemas/news.py`를 생성한다:

```python
class NewsArticle(BaseModel):
    id: str                      # hash(url)
    title: str
    description: str | None
    source: str                  # 출처 (Reuters, Bloomberg 등)
    url: str
    published_at: str            # ISO 8601
    content_snippet: str | None  # 본문 일부
    data_source: str             # "newsapi" | "gdelt"

class NewsCollection(BaseModel):
    articles: list[NewsArticle]
    query_keywords: list[str]
    collected_at: str
    total_count: int
```

### 3. 데이터 캐싱
- 캐시 경로: `backend/data/raw/news/YYYY-MM-DD_newsapi.json`
- GDELT: `backend/data/raw/news/YYYY-MM-DD_gdelt.json`
- 뉴스는 하루 1회 수집 (무료 tier rate limit 대응)

### 4. DataCollector 통합
`DataCollector` 파사드에 뉴스 수집기를 추가한다:

```python
class DataCollector:
    def __init__(self):
        self.eia = EIACollector()
        self.fred = FREDCollector()
        self.news = NewsCollector()

    async def collect_news(self, max_articles: int = 50) -> list[dict]:
        """뉴스 수집 (NewsAPI + GDELT 병합, 중복 제거)"""
        ...
```

### 5. 테스트
`backend/tests/test_news_collector.py`에 테스트를 작성한다:
- NewsAPI 응답 mocking
- GDELT 응답 mocking
- 중복 기사 제거 로직 테스트
- 키워드 쿼리 생성 테스트

## AC (Acceptance Criteria)
1. `NewsCollector`가 NewsAPI에서 유가 관련 기사를 수집한다
2. GDELT에서 에너지 관련 이벤트를 수집한다
3. 두 소스의 기사가 병합되고 중복이 제거된다
4. 캐시가 정상 동작한다 (하루 1회 제한)
5. `pytest backend/tests/test_news_collector.py` 가 통과한다
