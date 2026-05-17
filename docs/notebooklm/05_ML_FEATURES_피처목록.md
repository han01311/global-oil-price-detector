# OilLens XGBoost 모델 피처 목록

이 문서는 `FeatureEngineer` 서비스(`backend/app/services/feature_engineering.py`)에서 생성되는 머신러닝 피처를 설명합니다.

> **Note**: 모든 피처는 **유종별 독립 생성**됩니다 (ADR-013). 즉, Dubai/Brent/WTI 각각에 대해 동일한 피처 구조가 개별적으로 생성됩니다. 아래 표기에서 `{crude}`는 `wti`, `brent`, `dubai` 중 하나입니다.

## 1. 가격 기반 피처 (Price-based Features)

- `{crude}_price`: 유종별 현물가 (USD/bbl). forward-fill + backward-fill 적용.

## 2. 유종 간 스프레드 (Cross-Crude Spreads)

- `wti_brent_spread`: WTI와 Brent 가격 스프레드 (`wti` - `brent`)
- `dubai_brent_spread`: Dubai와 Brent 가격 스프레드 (`dubai` - `brent`)
- `wti_dubai_spread`: WTI와 Dubai 가격 스프레드 (`wti` - `dubai`)

## 3. 이동평균 피처 (Moving Average Features)

- `{crude}_ma{N}`: 유종별 N일 이동평균 (N = 5, 10, 20, 50)
- `{crude}_ma{N}_ratio`: 현재 가격과 N일 이동평균의 비율. 추세 대비 현재 가격 수준을 나타냄.

## 4. 변동률 피처 (Return Features)

- `{crude}_return_{N}d`: N일 전 대비 유종별 가격 변동률 (N = 1, 5, 10, 20). 모멘텀 지표.

## 5. 변동성 피처 (Volatility Features)

- `{crude}_vol_10d`: 유종별 일일 변동률의 10일 롤링 표준편차. 단기 시장 변동성 지표.
- `{crude}_vol_20d`: 유종별 일일 변동률의 20일 롤링 표준편차. 중기 시장 변동성 지표.

## 6. 거시경제 피처 (Macroeconomic Features)

- `fed_rate`: 미국 연방기금금리 (월별 데이터를 ffill하여 일별로 변환)
- `dollar_index`: 미국 달러 인덱스
- `yield_spread`: 미국 장단기 국채 금리차 (10년물 - 2년물)
- `krw_usd`: KRW/USD 원-달러 매매기준율 (한국수출입은행 공공데이터 API, 일별)
- `krw_usd_change_5d`: KRW/USD 환율의 5일 전 대비 변동률 (%). 환율 모멘텀 지표.

## 7. 래깅 피처 (Lagged Features)

- `fed_rate_lag5`: 연방기금금리의 5일 전 래깅 값. 정보 반영 시차를 고려.
- `dollar_index_lag5`: 달러 인덱스의 5일 전 래깅 값.
- `krw_usd_lag5`: 원-달러 환율의 5일 전 래깅 값.

> 래깅 피처는 미래 정보 누출(data leakage)을 방지하기 위해 적용됩니다.

## 8. 타겟 변수 (Target Variables)

- `target_{crude}_7d`: 유종별 7일 후 가격 변동률 (예측 목표)
- `target_{crude}_30d`: 유종별 30일 후 가격 변동률 (예측 목표)
- `target_7d`: 레거시 호환용 WTI 7일 후 변동률 (= `target_wti_7d`)
- `target_30d`: 레거시 호환용 WTI 30일 후 변동률 (= `target_wti_30d`)

---

## 피처 생성 파이프라인 요약

```
[Input] oil_prices (Dubai/Brent/WTI) + macro_indicators (fed_rate, dollar_index, yield_spread, krw_usd)
    ↓
[FeatureEngineer.build_features()]
    ↓  ffill + bfill (가격 결측치 보간)
    ↓  유종별 독립 피처 생성 (3유종 × 이동평균/변동률/변동성)
    ↓  유종 간 스프레드 산출 (3개)
    ↓  거시경제 피처 병합 + 래깅
    ↓  inf → NaN 변환 + dropna
    ↓
[Output] 학습 가능한 DataFrame (float 타입, 날짜 인덱스)
```

## 총 피처 수 (추정)

| 카테고리 | 피처 수 |
|----------|---------|
| 가격 기반 | 3 (유종별 × 1) |
| 유종 간 스프레드 | 3 |
| 이동평균 + 비율 | 24 (유종별 × 4윈도우 × 2) |
| 변동률 | 12 (유종별 × 4래그) |
| 변동성 | 6 (유종별 × 2윈도우) |
| 거시경제 | 5 (fed_rate, dollar_index, yield_spread, krw_usd, krw_usd_change_5d) |
| 래깅 | 3 (fed_rate_lag5, dollar_index_lag5, krw_usd_lag5) |
| **합계** | **~56개** |
