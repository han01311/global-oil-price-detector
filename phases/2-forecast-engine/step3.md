# Step 3: 뉴스 기반 보정(Premium/Discount) 로직 구현

## 목표
XGBoost 베이스라인에 뉴스 분석 결과를 반영하여 최종 추정 유가 밴드를 산출하는 보정 로직을 구현한다.

## 핵심 로직
```
Final Price = Current Price × (1 + Baseline Change%) × (1 + News Adjustment%)
Confidence Band = ± (Model RMSE + News Uncertainty Factor)
```

## 작업

### 1. 뉴스 보정 로직
`backend/app/services/forecast_engine.py`에 추가:

```python
class NewsAdjuster:
    """뉴스 기반 유가 보정 로직"""

    async def calculate_adjustment(self, classified_articles: list[dict],
                                    similar_events: list[dict]) -> dict:
        """뉴스 분석 결과를 기반으로 보정값 산출"""

        # 1. 현재 뉴스 기반 종합 감성
        weighted_score = sum(
            a["impact_score"] * a["confidence"]
            for a in classified_articles
            if a["is_relevant"]
        )
        article_count = sum(1 for a in classified_articles if a["is_relevant"])
        avg_sentiment = weighted_score / max(article_count, 1)

        # 2. 유사 과거 사례 기반 보정
        # 유사 사례의 실제 유가 변동률 가중 평균
        similar_adjustment = self._calculate_similar_adjustment(similar_events)

        # 3. 최종 보정값 = 감성 기반 + 유사 사례 기반 (가중 결합)
        # 감성 기반 가중치: 0.4, 유사 사례 가중치: 0.6
        news_adjustment = (
            0.4 * self._sentiment_to_pct(avg_sentiment) +
            0.6 * similar_adjustment
        )

        # 4. 불확실성 (뉴스 분산이 크면 신뢰구간 넓힘)
        uncertainty = self._calculate_uncertainty(classified_articles)

        return {
            "news_adjustment_pct": news_adjustment,     # 예: 0.015 = +1.5%
            "sentiment_component": avg_sentiment,
            "similar_component": similar_adjustment,
            "uncertainty_factor": uncertainty,
            "article_count": article_count,
            "dominant_category": self._get_dominant_category(classified_articles),
        }

    def _sentiment_to_pct(self, score: float) -> float:
        """감성 스코어(-5~+5)를 변동률(%)로 변환"""
        # 비선형 매핑: score ±1 → ±0.5%, ±3 → ±2%, ±5 → ±5%
        ...

    def _calculate_similar_adjustment(self, events: list[dict]) -> float:
        """유사 사례의 유가 변동률 가중 평균"""
        # 유사도가 높을수록 높은 가중치
        ...

    def _calculate_uncertainty(self, articles: list[dict]) -> float:
        """뉴스 의견 분산으로 불확실성 계산"""
        ...
```

### 2. 최종 추정 결과 통합
`backend/app/services/forecast_engine.py`에 추가:

```python
class HybridForecaster:
    """하이브리드 유가 추정기 (XGBoost + 뉴스 보정)"""

    async def forecast(self, current_price: float) -> ForecastResult:
        """최종 유가 추정 밴드 산출"""
        # 1. XGBoost baseline
        baseline = self.engine.predict(features)

        # 2. 뉴스 보정
        adjustment = await self.adjuster.calculate_adjustment(articles, similar)

        # 3. 최종 계산
        final_change_7d = baseline["baseline_change_7d"] + adjustment["news_adjustment_pct"]
        estimated_price_7d = current_price * (1 + final_change_7d)

        # 4. 신뢰구간
        band_width = baseline["model_rmse_7d"] + adjustment["uncertainty_factor"]

        return ForecastResult(
            current_price=current_price,
            estimated_7d=estimated_price_7d,
            estimated_7d_high=estimated_price_7d * (1 + band_width),
            estimated_7d_low=estimated_price_7d * (1 - band_width),
            baseline_change=baseline["baseline_change_7d"],
            news_adjustment=adjustment["news_adjustment_pct"],
            confidence=1 - adjustment["uncertainty_factor"],
            dominant_factor=adjustment["dominant_category"],
        )
```

### 3. 스키마
`backend/app/schemas/forecast.py`를 생성:

```python
class ForecastResult(BaseModel):
    current_price: float
    estimated_7d: float
    estimated_7d_high: float
    estimated_7d_low: float
    estimated_30d: float
    estimated_30d_high: float
    estimated_30d_low: float
    baseline_change_7d: float
    baseline_change_30d: float
    news_adjustment_pct: float
    confidence: float               # 0~1
    dominant_factor: str            # 주요 영향 요인
    factor_breakdown: list[dict]    # 카테고리별 기여도
    generated_at: str
```

### 4. 테스트
`backend/tests/test_news_adjuster.py`:
- 감성→변동률 변환 정확도
- 유사 사례 가중 평균 계산
- 불확실성 계산
- 최종 밴드 산출 정합성

## AC (Acceptance Criteria)
1. 뉴스 보정값이 감성 스코어와 유사 사례를 기반으로 산출된다
2. 최종 추정 가격 = 현재가 × (1 + baseline) × (1 + news adjustment)
3. 신뢰구간(밴드)이 불확실성을 반영한다
4. `ForecastResult` 스키마로 구조화된 결과가 반환된다
5. `pytest backend/tests/test_news_adjuster.py` 가 통과한다
