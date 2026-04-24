# Step 2: XGBoost 베이스라인 모델 학습

## 목표
피처 엔지니어링된 데이터로 XGBoost 모델을 학습하여 7일/30일 유가 변동률을 예측하는 베이스라인 모델을 구축한다.

## 작업

### 1. 추정 엔진 서비스
`backend/app/services/forecast_engine.py`를 구현한다:

```python
class ForecastEngine:
    """XGBoost 기반 유가 추정 엔진"""

    MODEL_DIR = Path("backend/ml/models")

    def train(self, features_df: pd.DataFrame) -> dict:
        """모델 학습 및 평가"""
        train, test = FeatureEngineer().split_train_test(features_df)

        # 피처와 타겟 분리
        feature_cols = [c for c in train.columns if not c.startswith("target_")]
        X_train, y_train_7d = train[feature_cols], train["target_7d"]
        X_test, y_test_7d = test[feature_cols], test["target_7d"]

        # XGBoost 학습
        model_7d = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
        )
        model_7d.fit(X_train, y_train_7d,
                     eval_set=[(X_test, y_test_7d)],
                     verbose=False)

        # 동일하게 30d 모델도 학습
        ...

        # 모델 저장
        joblib.dump(model_7d, self.MODEL_DIR / "xgb_7d.joblib")
        joblib.dump(model_30d, self.MODEL_DIR / "xgb_30d.joblib")

        # 평가 지표 반환
        return {
            "rmse_7d": ...,
            "mae_7d": ...,
            "rmse_30d": ...,
            "mae_30d": ...,
            "feature_importance": dict(zip(feature_cols, model_7d.feature_importances_)),
        }

    def predict(self, current_features: pd.DataFrame) -> dict:
        """현재 데이터로 유가 변동률 예측"""
        model_7d = joblib.load(self.MODEL_DIR / "xgb_7d.joblib")
        model_30d = joblib.load(self.MODEL_DIR / "xgb_30d.joblib")

        pred_7d = model_7d.predict(current_features)[0]
        pred_30d = model_30d.predict(current_features)[0]

        return {
            "baseline_change_7d": float(pred_7d),   # 예: 0.023 = +2.3%
            "baseline_change_30d": float(pred_30d),
            "model_rmse_7d": ...,  # 학습 시 기록된 RMSE
        }
```

### 2. 학습 스크립트
```bash
cd backend && python -m app.services.forecast_engine --train
```
독립 실행 가능한 학습 스크립트를 포함한다.

### 3. 모델 평가 리포트
학습 결과를 `backend/ml/training_report.json`에 저장:
```json
{
  "trained_at": "...",
  "data_range": "2020-01-01 ~ 2024-12-31",
  "samples": 1250,
  "rmse_7d": 0.032,
  "mae_7d": 0.024,
  "top_features": ["wti_ma5_ratio", "dollar_index", ...]
}
```

### 4. 테스트
`backend/tests/test_forecast_engine.py`:
- 모델 학습 → 저장 → 로드 → 예측 흐름
- 예측값 범위 검증 (비현실적 값 감지)
- 피처 중요도 산출 검증

## AC (Acceptance Criteria)
1. XGBoost 모델이 학습되고 `backend/ml/models/`에 저장된다
2. 7일/30일 변동률 예측값이 산출된다
3. RMSE/MAE 평가 지표가 기록된다
4. 피처 중요도가 산출된다
5. `pytest backend/tests/test_forecast_engine.py` 가 통과한다
