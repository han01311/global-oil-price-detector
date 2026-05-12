# OilLens XGBoost 모델 피처 목록

이 문서는 `FeatureEngineer` 서비스에서 생성되는 머신러닝 피처를 설명합니다.

## 1. 가격 기반 피처 (Price-based Features)

- `wti_price`: WTI 현물가 (USD/bbl)
- `brent_price`: Brent 현물가 (USD/bbl)
- `wti_brent_spread`: WTI와 Brent 가격 스프레드 (`wti` - `brent`)

## 2. 이동평균 피처 (Moving Average Features)

- `wti_ma{N}`: WTI 가격의 N일 이동평균 (N = 5, 10, 20, 50)
- `wti_ma{N}_ratio`: 현재 WTI 가격과 N일 이동평균의 비율. 추세 대비 현재 가격 수준을 나타냄.

## 3. 변동률 피처 (Return Features)

- `wti_return_{N}d`: N일 전 대비 WTI 가격 변동률 (N = 1, 5, 10, 20). 모멘텀 지표.

## 4. 변동성 피처 (Volatility Features)

- `wti_vol_{N}d`: WTI 일일 변동률의 N일 롤링 표준편차 (N = 10, 20). 시장 변동성 지표.

## 5. 거시경제 피처 (Macroeconomic Features)

- `fed_rate`: 미국 연방기금금리 (월별 데이터를 ffill하여 일별로 변환)
- `dollar_index`: 미국 달러 인덱스
- `yield_spread`: 미국 장단기 국채 금리차 (10년물 - 2년물)
- `krw_usd`: KRW/USD 원-달러 매매기준율 (한국수출입은행 공공데이터 API, 일별)
- `{macro_feature}_lag5`: 거시경제 지표의 5일 전 래깅 값. 정보 반영 시차를 고려.
- `krw_usd_change_5d`: KRW/USD 환율의 5일 전 대비 변동률 (%). 환율 모멘텀 지표.

## 6. 타겟 변수 (Target Variables)

- `target_7d`: 7일 후 WTI 가격 변동률 (예측 목표)
- `target_30d`: 30일 후 WTI 가격 변동률 (예측 목표)
