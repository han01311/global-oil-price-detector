# Step 1: Feature Engineering 파이프라인 구현

## 목표
EIA 유가 + FRED 거시경제 + Baker Hughes 리그 데이터를 XGBoost 학습에 사용할 피처로 변환하는 파이프라인을 구현한다.

## 작업

### 1. Feature Engineering 서비스
`backend/app/services/feature_engineering.py`를 구현한다:

```python
class FeatureEngineer:
    """시계열 피처 엔지니어링 파이프라인"""

    def build_features(self, prices_df: pd.DataFrame,
                       macro_df: pd.DataFrame) -> pd.DataFrame:
        """원시 데이터를 ML 피처로 변환"""
        features = pd.DataFrame()

        # 1. 가격 피처
        features["wti_price"] = prices_df["wti"]
        features["brent_price"] = prices_df["brent"]
        features["wti_brent_spread"] = prices_df["wti"] - prices_df["brent"]

        # 2. 이동평균
        for window in [5, 10, 20, 50]:
            features[f"wti_ma{window}"] = prices_df["wti"].rolling(window).mean()
            features[f"wti_ma{window}_ratio"] = prices_df["wti"] / features[f"wti_ma{window}"]

        # 3. 변동률
        for lag in [1, 5, 10, 20]:
            features[f"wti_return_{lag}d"] = prices_df["wti"].pct_change(lag)

        # 4. 변동성 (rolling std)
        features["wti_vol_10d"] = prices_df["wti"].pct_change().rolling(10).std()
        features["wti_vol_20d"] = prices_df["wti"].pct_change().rolling(20).std()

        # 5. 거시경제 피처 (forward fill for frequency mismatch)
        features["fed_rate"] = macro_df["fed_rate"].ffill()
        features["dollar_index"] = macro_df["dollar_index"].ffill()
        features["yield_spread"] = macro_df["yield_spread"].ffill()

        # 6. 래깅 피처 (미래 정보 누출 방지)
        for col in ["fed_rate", "dollar_index"]:
            features[f"{col}_lag5"] = features[col].shift(5)

        # 7. 타겟 변수
        features["target_7d"] = prices_df["wti"].shift(-7) / prices_df["wti"] - 1
        features["target_30d"] = prices_df["wti"].shift(-30) / prices_df["wti"] - 1

        return features.dropna()

    def split_train_test(self, features_df: pd.DataFrame,
                         test_ratio: float = 0.2) -> tuple:
        """시계열 특성을 고려한 순차 분할 (랜덤 셔플 금지)"""
        split_idx = int(len(features_df) * (1 - test_ratio))
        train = features_df.iloc[:split_idx]
        test = features_df.iloc[split_idx:]
        return train, test
```

### 2. 피처 목록 문서화
어떤 피처가 사용되는지 `backend/ml/FEATURES.md`에 정리한다.

### 3. 테스트
`backend/tests/test_feature_engineering.py`:
- 피처 개수 확인
- NaN 처리 검증
- 미래 정보 누출 없음 확인 (타겟 변수가 래깅되어 있는지)
- 시계열 분할이 순차적인지 확인

## AC (Acceptance Criteria)
1. 원시 데이터로부터 최소 20개 이상의 피처가 생성된다
2. NaN이 적절히 처리된다 (dropna 또는 ffill)
3. 미래 정보 누출이 없다 (타겟 변수가 미래 데이터를 shift)
4. train/test 분할이 시계열 순서를 유지한다
5. `pytest backend/tests/test_feature_engineering.py` 가 통과한다
