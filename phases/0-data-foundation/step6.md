# Step 6: 데이터 파이프라인 통합 테스트

## 목표
Phase 0에서 구현한 모든 데이터 수집기와 API 엔드포인트를 통합적으로 검증한다.

## 작업

### 1. 통합 테스트 작성
`backend/tests/test_data_pipeline.py`를 작성한다:

```python
class TestDataPipeline:
    """데이터 파이프라인 전체 흐름 통합 테스트"""

    async def test_full_collection_flow(self):
        """DataCollector를 통한 전체 수집 흐름"""
        collector = DataCollector()
        result = await collector.collect_all(
            start_date="2024-01-01",
            end_date="2024-01-31"
        )
        assert "prices" in result
        assert "macro" in result
        ...

    async def test_cache_invalidation(self):
        """캐시 만료 후 재수집 동작 확인"""
        ...

    async def test_api_key_missing_handling(self):
        """API 키 누락 시 그레이스풀 처리"""
        ...
```

### 2. 전체 테스트 실행
```bash
cd backend && pytest -v
```
모든 테스트가 통과하는지 확인한다.

### 3. index.json 업데이트
`phases/0-data-foundation/index.json`의 모든 step이 completed인지 확인한다.

## AC (Acceptance Criteria)
1. `pytest backend/ -v`에서 모든 테스트가 통과한다
2. DataCollector가 EIA + FRED + News를 병렬로 수집할 수 있다
3. API 키 누락 시 서버가 크래시하지 않고 적절한 에러를 반환한다
4. 캐시 메커니즘이 rate limit을 보호한다
5. 전체 데이터 수집→API 응답 흐름이 정상 동작한다
