# Step 6: 추정 엔진 통합 테스트

## 목표
Phase 2에서 구현한 전체 추정 파이프라인을 통합적으로 검증한다.

## 작업

### 1. 통합 테스트

```python
class TestForecastIntegration:

    async def test_full_forecast_pipeline(self):
        """데이터 수집 → 피처 생성 → 예측 → 보정 → 최종 추정"""
        ...

    async def test_forecast_with_news_adjustment(self):
        """뉴스 보정이 적용된 추정 결과 vs 베이스라인 비교"""
        ...

    async def test_briefing_includes_forecast(self):
        """브리핑에 추정 수치가 포함되는지 확인"""
        ...

    async def test_confidence_band_reasonableness(self):
        """신뢰구간이 비현실적으로 크거나 작지 않은지 확인"""
        ...
```

### 2. 전체 테스트 실행
```bash
cd backend && pytest -v
```

### 3. 모델 성능 검증
- 학습 리포트 확인
- 피처 중요도 상위 항목이 의미적으로 합리적인지 확인

## AC (Acceptance Criteria)
1. `pytest backend/ -v`에서 모든 테스트가 통과한다
2. 전체 파이프라인(수집→피처→예측→보정→브리핑)이 동작한다
3. 추정 결과가 비현실적이지 않다 (변동률 ±50% 이내 등)
4. 브리핑이 추정 근거를 설명한다
5. 모델 학습 리포트가 저장되어 있다
