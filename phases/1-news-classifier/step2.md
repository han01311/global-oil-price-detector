# Step 2: ChromaDB Market Memory 구축

## 목표
분류된 뉴스 기사와 해당 시점의 유가 변동률을 벡터 DB(ChromaDB)에 적재하여, 과거 유사 사례를 즉시 검색할 수 있는 Market Memory 시스템을 구축한다.

## 작업

### 1. Market Memory 서비스
`backend/app/services/market_memory.py`를 구현한다:

```python
class MarketMemory:
    """ChromaDB 기반 과거 사례 벡터 검색 시스템"""

    COLLECTION_NAME = "oil_market_events"

    def __init__(self):
        self._client = chromadb.PersistentClient(path="backend/data/chromadb")
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

    async def store_event(self, classified_article: dict, price_change: dict):
        """분류된 기사 + 유가 변동률을 벡터 DB에 저장"""
        # document: 기사 제목 + 영향 요약
        # metadata:
        #   - category, impact_score, confidence
        #   - date, wti_change_pct, brent_change_pct
        #   - wti_change_1d, wti_change_7d, wti_change_30d
        ...

    async def search_similar(self, query: str, category: str = None,
                              n_results: int = 5) -> list[dict]:
        """유사 과거 사례 검색"""
        # query: 현재 뉴스 제목 또는 요약
        # category 필터 선택적 적용
        # 결과에 당시 유가 변동률 포함
        ...

    async def get_category_stats(self) -> dict:
        """카테고리별 적재 건수 및 평균 Impact Score"""
        ...
```

### 2. 유가 변동률 계산 유틸
`backend/app/utils/price_utils.py`를 생성:

```python
def calculate_price_changes(prices_df: pd.DataFrame, event_date: str) -> dict:
    """이벤트 발생 시점 기준 유가 변동률 계산"""
    # 1일, 7일, 30일 변동률 (%)
    # event_date 전후 데이터 활용
    return {
        "wti_change_1d": ...,
        "wti_change_7d": ...,
        "wti_change_30d": ...,
        "brent_change_1d": ...,
        "brent_change_7d": ...,
        "brent_change_30d": ...,
    }
```

### 3. 테스트
`backend/tests/test_market_memory.py`:
- ChromaDB 저장/검색 기본 동작
- 카테고리 필터 검색 테스트
- 유사도 기반 정렬 검증
- 유가 변동률 계산 정확도

## AC (Acceptance Criteria)
1. 분류된 기사를 ChromaDB에 저장할 수 있다
2. 유사 텍스트로 검색 시 관련 과거 사례가 반환된다
3. 카테고리 필터링이 정상 동작한다
4. 반환 결과에 당시 유가 변동률(1d/7d/30d)이 포함된다
5. `pytest backend/tests/test_market_memory.py` 가 통과한다
