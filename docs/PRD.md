# PRD: 글로벌 유가 추정 및 AX 대시보드 (Petro-AX)

## 목표
오피넷 정량 지표와 다차원 요인으로 분류된 뉴스 데이터를 결합한 하이브리드 모델을 통해 국제 유가를 추정하고, 그 변동의 근본 원인과 신뢰도 높은 단기 전망을 제공하는 비즈니스 인사이트 대시보드를 구축한다.

## 사용자
원유 수급 리스크를 선제적으로 파악하고 대응해야 하는 에너지/제조업 B2B 실무자 및 시장 분석가.

---

## 핵심 기능

### F1. 하이브리드 유가 추정 엔진 (Hybrid Forecasting Engine)

#### F1-a. 정량적 베이스라인 추정
- 오피넷(과거 유가), EIA(수급/재고), FRED(거시경제) 데이터를 시계열 머신러닝 모델(XGBoost)에 학습
- 기본적인 유가 추세선(Baseline)을 예측하여 **7일 / 30일 단기 전망** 제공

#### F1-b. 정성적 보정 (News Premium/Discount)
- 벡터 DB(ChromaDB)에 적재된 뉴스 요인 분석 결과(지정학, 공급 리스크 등)를 기반으로
- 현재 이슈가 유가에 미칠 상승/하락 압력(%)을 Gemini가 계산
- **최종 추정 유가 밴드(Range)** 산출: `Baseline ± News Adjustment`
- 신뢰구간(Confidence Band)을 시각적으로 표시

### F2. AI 스마트 필터 및 다차원 요인 분류기

- 글로벌 뉴스 중 유가 영향 기사만 자동 선별 (Gemini 기반 relevance scoring)
- 근본 원인을 6대 카테고리로 분류:
  - `geopolitics` (지정학: 전쟁, 제재, 외교)
  - `supply` (공급: OPEC 감산, 셰일, 시추)
  - `demand` (수요: 경기, 계절, 소비)
  - `macro` (거시경제: 금리, 달러, 인플레이션)
  - `climate` (기후/ESG: 허리케인, 탄소정책)
  - `speculation` (투기/심리: 포지션, 선물시장)
- 각 기사에 **영향도 스코어(Impact Score: -5 ~ +5)** 및 JSON 메타데이터 부여

### F3. 다이나믹 뉴스 익스플로러 & 과거 사례 매핑 (Market Memory)

- 과거 기사 발생 시점의 실제 유가 변동률을 매핑하여 벡터 DB에 적재
- 대시보드 차트에서 **핀포인트 클릭** 시 해당 시점의 요인별 기사 조회
- 태그별 (예: `#geopolitics`) 과거 유사 사례 즉각 검색
- "2019년 사우디 아람코 피격 당시 +15% → 현재 유사 패턴 감지" 등 유사도 기반 매핑

### F4. AI 유가 브리핑 자동 생성

- 추정 엔진 산출 수치 + 벡터 DB 유사 과거 사례를 종합
- "왜 이런 가격을 추정했는지" 설명하는 **일일 전망 리포트** 자동 생성
- Gemini가 작성하되, 구조화된 포맷(요약 → 핵심 요인 → 리스크 시나리오)으로 출력

---

## 데이터 소스

### 정량 데이터 (Quantitative)

| 소스 | 제공 데이터 | 접근 방식 | 비용 |
|------|-------------|-----------|------|
| **EIA API v2** | WTI/Brent 일별 현물가, 미국 원유 재고(주간), 생산량, 수출입 | REST API (무료 키 발급) | 무료 |
| **FRED API** | 연방기금금리(`FEDFUNDS`), 미국 달러 인덱스(`DTWEXBGS`), CPI, 산업생산지수 | REST API (무료 키 발급) | 무료 |
| **오피넷 API** | 국내 유종별 평균 유가, 지역별 가격 | REST API (인증키 신청) | 무료 |
| **World Bank API** | 월별 원자재 가격(Pink Sheet), 글로벌 GDP | REST API (키 불필요) | 무료 |
| **Baker Hughes** | 주간 글로벌 시추 리그 수 (Rig Count) | 엑셀 다운로드 → 파싱 | 무료 |

### 정성 데이터 (Qualitative / News)

| 소스 | 제공 데이터 | 접근 방식 | 비용 |
|------|-------------|-----------|------|
| **GDELT Project** | 1979년~ 글로벌 이벤트 DB, 지정학 이벤트 분류(CAMEO 코드), 톤/감성 | BigQuery 또는 REST API | 무료 (BQ 프리티어) |
| **NewsAPI.org** | 실시간 글로벌 뉴스 헤드라인 + 메타데이터 | REST API | 무료 (100회/일) |
| **GNews API** | 실시간 뉴스 헤드라인 (NewsAPI 대체/보완) | REST API | 무료 (100회/일) |

### 파생 데이터 (Derived / Computed)

| 데이터 | 산출 방식 |
|--------|-----------|
| 뉴스 요인 분류 JSON | Gemini API로 기사 분석 → 6대 카테고리 + Impact Score |
| 과거 사례 벡터 | 뉴스 임베딩 + 당시 유가 변동률 → ChromaDB 적재 |
| 유사도 매핑 | 최신 뉴스 벡터 vs 과거 사례 벡터 cosine similarity |
| 추정 유가 밴드 | XGBoost baseline ± Gemini news adjustment |

---

## 추정 엔진 로직 (상세)

```
[Phase 1: Baseline]
  EIA(유가/재고) + FRED(금리/달러) + Baker Hughes(리그수)
  → Feature Engineering (이동평균, 변동률, 래깅)
  → XGBoost 학습/예측
  → Baseline Forecast (7일/30일)

[Phase 2: News Adjustment]
  NewsAPI/GDELT → Gemini 요인 분류 → Impact Score 산출
  → ChromaDB에서 유사 과거 사례 검색
  → 과거 사례의 실제 유가 변동률 참조
  → News Premium/Discount (%) 산출

[Phase 3: Final Estimate]
  Final Price = Baseline × (1 + News Adjustment%)
  Confidence Band = ± (모델 RMSE + 뉴스 불확실성)
```

---

## MVP 제외 사항
- 위성 이미지/선박 AIS 등 물리적 대체 데이터 원시 수집
- 정저압(BHP) 등 극히 제한된 업스트림 물리 데이터의 직접 모델링
- 초단타 매매(HFT)를 위한 자동 매매 시스템
- OPEC 월간보고서 자동 파싱 (수동 다운로드는 가능)
- 실시간 선물/옵션 시장 데이터 연동 (CME 등 유료)

## 디자인
- **방향**: 다크모드 고정, 프로페셔널한 금융 터미널 스타일
- **UI 요소**: 유가 추정 차트(상하한 밴드 표시), 기사 카테고리별 뱃지(Badge)
- **색상**: 무채색 베이스 + 상승(네온 오렌지 `#FF6B35`) / 하락(사이버 블루 `#00D4FF`) 포인트
- **서체**: Inter (Latin) + Pretendard (Korean)
- **차트**: 캔들스틱 + 신뢰구간 밴드, 뉴스 핀포인트 마커
