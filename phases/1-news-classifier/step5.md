# Step 5: 분류기 통합 테스트

## 목표
Phase 1에서 구현한 뉴스 분류기, Market Memory, API를 통합적으로 검증한다.

## 작업

### 1. 통합 테스트
`backend/tests/test_classifier_integration.py`:

```python
class TestClassifierIntegration:
    """뉴스 분류 파이프라인 전체 흐름 통합 테스트"""

    async def test_full_classification_flow(self):
        """뉴스 수집 → 분류 → ChromaDB 적재 → 검색"""
        ...

    async def test_factor_summary_accuracy(self):
        """요인 요약이 분류된 기사의 통계와 일치하는지 확인"""
        ...

    async def test_similar_event_relevance(self):
        """유사 사례 검색 결과가 쿼리와 관련성이 있는지 확인"""
        ...
```

### 2. 전체 테스트 실행
```bash
cd backend && pytest -v
```

### 3. 데이터 품질 확인
- ChromaDB에 적재된 이벤트 수 확인
- 카테고리별 분포 확인
- 잘못 분류된 사례가 없는지 샘플 검증

## AC (Acceptance Criteria)
1. `pytest backend/ -v`에서 모든 테스트가 통과한다
2. 뉴스 수집→분류→적재→검색 전체 파이프라인이 동작한다
3. ChromaDB에 시드 데이터가 정상 적재되어 있다
4. 유사 사례 검색 결과가 의미적으로 관련성이 있다
5. 요인 요약이 정확한 통계를 반환한다
