# 아키텍처

## 디렉토리 구조
```
global-oil-price-detector/
├── frontend/                    # React + TypeScript (Vite)
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard/       # 메인 대시보드 레이아웃 + 예측 비교 테이블
│   │   │   ├── PriceChart/      # 유가 차트 (캔들스틱 + 밴드)
│   │   │   ├── NewsExplorer/    # 뉴스 익스플로러 & 필터 + 유사 사례 팝업
│   │   │   ├── Briefing/        # AI 브리핑 뷰어
│   │   │   ├── FactorGauge/     # 6대 요인 게이지/레이더
│   │   │   ├── Admin/           # 관리자 대시보드 (Command Center, Pipeline, Data Hub, Operations)
│   │   │   └── common/          # 공통 UI (ErrorBoundary, Badge, Card, Skeleton 등)
│   │   ├── types/               # TypeScript 타입 정의
│   │   ├── hooks/               # Custom hooks (usePriceData, useNewsData, useBriefing, useDashboardData, useFactorSummary)
│   │   ├── services/            # API 호출 래퍼 (api.ts + adminApi.ts, 백엔드만 호출)
│   │   ├── context/             # React Context (DashboardContext, ToastContext)
│   │   ├── App.tsx              # 루트 컴포넌트
│   │   └── main.tsx             # 엔트리 포인트
│   └── public/                  # 정적 파일
│
├── backend/                     # FastAPI (Python)
│   ├── app/
│   │   ├── api/                 # API 라우트 핸들러 (Presentation)
│   │   │   ├── prices.py        # 유가 데이터 엔드포인트
│   │   │   ├── news.py          # 뉴스 분류/검색 엔드포인트
│   │   │   ├── forecast.py      # 예측 엔진 엔드포인트
│   │   │   ├── briefing.py      # AI 브리핑 엔드포인트
│   │   │   ├── public_data.py   # 공공데이터 API (환율, 수입집중도, 데이터소스)
│   │   │   └── admin.py         # 관리자 API (모니터링, 파이프라인, 크롤링, Gap Recovery)
│   │   ├── core/                # 설정, 보안, 미들웨어, 글로벌 에러 래퍼
│   │   │   ├── config.py        # 환경변수, API 키 관리
│   │   │   └── database.py      # PostgreSQL 비동기 DB 엔진 (SQLAlchemy + asyncpg)
│   │   ├── models/              # DB 모델 (SQLAlchemy ORM)
│   │   │   ├── oil_price.py     # 유가 테이블
│   │   │   ├── news_article.py  # 뉴스 기사 테이블
│   │   │   ├── oil_inventory.py # 재고 테이블
│   │   │   ├── oil_production.py# 생산량 테이블
│   │   │   ├── macro_indicator.py# 거시경제 지표 테이블 (krw_usd 포함)
│   │   │   ├── oil_import.py    # 한국석유공사 원유수입 국가별 테이블
│   │   │   ├── world_oil_trade.py# 한국석유공사 세계 원유 수출입 물량 테이블
│   │   │   ├── collection_log.py# 수집 이력 로그 테이블
│   │   │   ├── pipeline_job.py  # 파이프라인 작업 이력 테이블
│   │   │   └── rate_limit_counter.py # API Rate Limit 카운터 테이블
│   │   ├── schemas/             # Pydantic 스키마 (데이터 Validation)
│   │   │   ├── price.py         # 유가 데이터 스키마
│   │   │   ├── news.py          # 뉴스/요인 분류 스키마
│   │   │   ├── forecast.py      # 예측 결과 + 브리핑 스키마
│   │   │   └── admin.py         # 관리자 API 응답 스키마
│   │   ├── services/            # 비즈니스 로직 + AI 서비스
│   │   │   ├── data_collector.py       # 외부 API 데이터 수집기 (NYT, Guardian, EIA, FRED, Opinet)
│   │   │   ├── opinet_collector.py     # 한국석유공사 오피넷 유가 스크래핑 수집기
│   │   │   ├── news_classifier.py      # Gemma 4 뉴스 요인 분류기 (Ollama 로컬 LLM)
│   │   │   ├── forecast_engine.py      # XGBoost 기반 AI Quant 예측 엔진 (Method A)
│   │   │   ├── fundamental_forecast.py # 수급 기반 펀더멘탈 예측 엔진 (Method B)
│   │   │   ├── feature_engineering.py  # 시계열 피처 엔지니어링 파이프라인
│   │   │   ├── market_memory.py        # ChromaDB 벡터 검색 (유사 사례 탐색)
│   │   │   ├── briefing_generator.py   # AI 일일 브리핑 생성기 (Gemma 4)
│   │   │   ├── scheduler.py            # APScheduler 데이터 수집 자동화 스케줄러
│   │   │   ├── gap_recovery.py         # 데이터 누락 진단 및 자동 복구 서비스
│   │   │   ├── rate_limiter.py         # API별 Rate Limit 중앙 관리 + Exponential Backoff
│   │   │   ├── exchange_rate_collector.py # 한국수출입은행 환율 API 수집기 (data.go.kr)
│   │   │   ├── import_concentration.py  # 수입 집중도(HHI) 분석 서비스 (KNOC 공공데이터)
│   │   │   ├── archive_crawler.py      # 과거 뉴스 아카이브 크롤러 (OilPrice.com)
│   │   │   └── historical_loader.py    # ChromaDB 시드 데이터 로더 (주요 유가 사건 30건)
│   │   ├── utils/               # 유틸리티
│   │   │   └── price_utils.py   # 유가 변동률 계산 유틸
│   │   └── main.py              # FastAPI 앱 인스턴스 + Lifespan 관리
│   ├── data/                    # 로컬 데이터 캐시 (Fallback 스토리지)
│   │   ├── raw/                 # 원시 API 응답 캐시 (일별 JSON + 환율 캐시)
│   │   ├── public/              # 공공데이터 CSV 원본 (KNOC 원유수입, 세계 수출입 물량)
│   │   └── processed/           # 전처리된 데이터
│   │       └── briefings/       # 일일 브리핑 캐시 (날짜별 JSON)
│   ├── ml/                      # ML 모델 아티팩트
│   │   └── models/              # 학습된 모델 파일 (.joblib)
│   ├── scripts/                 # 운영 스크립트
│   │   ├── run_ollama_classification.py   # Ollama(Gemma 4) 뉴스 일괄 분류
│   │   ├── run_gemini_classification.py   # Gemini API 뉴스 일괄 분류 (클라우드 Fallback)
│   │   ├── crawl_history.py               # 과거 뉴스 대량 크롤링 (NYT + Guardian)
│   │   ├── load_public_data.py            # data.go.kr CSV → PostgreSQL 적재 (KNOC 원유수입/세계교역)
│   │   ├── backfill_*.py                  # 데이터 보정 스크립트들
│   │   └── migrate_sqlite_to_pg.py        # SQLite → PostgreSQL 마이그레이션
│   └── tests/                   # pytest 테스트
│
├── docs/                        # 프로젝트 문서
├── scripts/                     # 하네스 스크립트
├── phases/                      # 하네스 phase 디렉토리
├── docker-compose.yml           # PostgreSQL 컨테이너 정의
└── GEMINI.md                    # 프로젝트 규칙
```

## 핵심 서비스 API 아키텍처

```
┌───────────────────────────────────────────────────────────────────┐
│                     Frontend (React + TypeScript)                  │
│ [ErrorBoundary]  Dashboard │ PriceChart │ Briefing │ FactorGauge  │
│                  NewsExplorer │ Admin (Command Center / Pipeline)  │
│ [Context] DashboardContext │ ToastContext                          │
└──────────────────────┬────────────────────────────────────────────┘
                       │ fetch (REST /w Timeout & Retry)
┌──────────────────────▼────────────────────────────────────────────┐
│                    Backend (FastAPI + Lifespan)                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ CORS Middleware │ Exception Handler (글로벌 에러 래퍼)       │  │
│  └───────────────────────┬──────────────────────────────────────┘  │
│  │ prices   │ │  news    │ │ forecast │ │brief- │ │ public │ │   admin    │ │
│  │  .py     │ │  .py     │ │   .py    │ │ing.py │ │_data.py│ │    .py     │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──┬────┘ └──┬────┘ └──────┬─────┘ │
│       │            │            │           │         │             │       │
│  ┌────▼────────────▼────────────▼───────────▼─────────▼─────────────▼────┐  │
│  │                     Service Layer                            │  │
│  │ data_collector     │ news_classifier     │ forecast_engine   │  │
│  │ opinet_collector   │ briefing_generator  │ fundamental_fore. │  │
│  │ feature_engineering│ market_memory       │ scheduler         │  │
│  │ rate_limiter       │ gap_recovery        │ archive_crawler   │  │
│  │ historical_loader  │ exchange_rate_coll. │ import_concentr.  │  │
│  └───┬──────────┬───────────┬──────────┬──────────┬────────┬───┘  │
│      │          │           │          │          │        │      │
└──────┼──────────┼───────────┼──────────┼──────────┼────────┼──────┘
       │          │           │          │          │        │
  ┌────▼───┐ ┌───▼─────┐ ┌──▼─────┐ ┌──▼───────┐ ┌▼──────┐ ┌▼────────────┐
  │External│ │ Ollama  │ │XGBoost │ │ ChromaDB │ │Postgr-│ │ Gemini API  │
  │  APIs  │ │(Gemma 4)│ │ Model  │ │ (Vector) │ │ eSQL   │ │ (Fallback)  │
  │NYT,Gua-│ │ 로컬LLM │ │ .jobl. │ │ 유사사례  │ │Docker │ │ 클라우드LLM  │
  │rdian,  │ │         │ │        │ │          │ │       │ │             │
  │EIA,FRED│ └─────────┘ └────────┘ └──────────┘ └───────┘ └─────────────┘
  │Opinet  │
  └────────┘
```

---

## 🛡️ 시스템 에러 핸들링 및 회복탄력성 (Resilience) 계층

시스템이 외부에 크게 의존하고 있기 때문에 API Rate Limit, 외부 서비스 다운, 예측 모델 오류에 대응하는 **회복탄력성 파이프라인**을 갖춥니다.

### 1. 외부 API 통신: Rate Limit 중앙 관리 + 캐시 Fallback
- `data_collector.py`는 Opinet, EIA, FRED, NYT, Guardian 등을 주기적으로 호출합니다.
- **Rate Limit 중앙 관리**: `rate_limiter.py`가 API별 일일 한도와 최소 호출 간격을 중앙에서 관리합니다.
  - EIA: 무제한 (1.5초 간격)
  - FRED: 무제한 (2.0초 간격)
  - NYT: 500회/일 (12.5초 간격, 분당 5회 제한)
  - Guardian: 5,000회/일 (1초 간격)
  - **한국수출입은행**: 1,000회/일 (1초 간격) — 공공데이터 포털 API 키 사용
  - 카운터는 PostgreSQL의 `rate_limit_counters` 테이블에 일별 기록됩니다.
- **Fail-over**: 장애나 Rate Limit 발생 시 즉시 오류 처리하지 않고, 백엔드 로컬의 최신 캐시(`backend/data/raw/`) 데이터를 자동으로 로드해 제공합니다. (Stale Data Serving 전략)
- **Exponential Backoff**: API 실패 시, `with_backoff()` 래퍼를 통해 재요청 주기를 지수적으로 증가시키며 재시도합니다. HTTP 429/500/502/503/504 에러를 자동 감지합니다.

### 2. 데이터 무결성 검증 (Data Validation) 파이프라인
머신러닝과 LLM에 오염된 데이터가 주입되어 크래시되는 현상을 막기 위해 강력한 검증 단계를 거칩니다.
- **Pydantic 스키마 검증**: 모든 들어오고 나가는 데이터는 Pydantic 스키마(`schemas/*.py`) 레이어를 통과합니다. 누락된 키, Null 값, 비정상적인 유가(예: 음수 가격) 등이 탐지되면 즉각 예외(`ValidationError`)를 던져 잘못된 모델 학습을 차단합니다.
- **LLM 응답 검증 (JSON Parsing Fallback)**: Gemma 4가 할루시네이션으로 인해 깨진 JSON을 내뱉을 경우, 정규식(`re.search`)을 통해 JSON 추출을 시도합니다. 회복 불가능할 시 해당 뉴스는 `[Unknown Category]`로 안전하게 드롭(Drop)시킵니다.
- **Gap Recovery 서비스**: `gap_recovery.py`가 각 데이터 소스별로 일별 수집 누락 여부를 자동 진단하고, 관리자가 누락 데이터를 선택적으로 복구할 수 있습니다.

### 3. 글로벌 에러 전파 원칙 (Error Propagation Flow)
- **백엔드**: Service Layer에서 발생한 에러는 FastAPI의 글로벌 예외 핸들러에서 포착됩니다. 클라이언트에게는 보안에 민감한 스택 트레이스를 은폐하고 표준화된 에러 응답을 전달합니다.
- **프론트엔드**: 컴포넌트별로 `React ErrorBoundary`를 배치합니다.
  - 특정 모듈(예: 뉴스 익스플로러)에 렌더링/데이터 오류 발생 시 대시보드 전체가 깨지지 않도록 해당 영역만 Fallback UI (Error State)로 전환 처리.

---

## 🤖 AI/LLM 통합 아키텍처

### 로컬 LLM (Primary): Ollama + Gemma 4
- **모델**: `gemma4:e4b` (Google Gemma 4, Ollama 로컬 호스팅)
- **용도**:
  - 뉴스 기사 6대 요인 분류 + 유종별(Dubai/Brent/WTI) 독립 영향도 평가 (`news_classifier.py`)
  - 일일 유가 브리핑 생성 — 핵심 요인, 리스크 시나리오, 전망 (`briefing_generator.py`)
  - 수동 입력 텍스트 AI 정리/파싱 (`admin.py` 내 recover 엔드포인트)
  - 기사 제목 한국어 번역 (분류 시 자동 수행)
- **엔드포인트**: `http://localhost:11434/api/generate`
- **동시성 제어**: `asyncio.Semaphore(2)`로 동시 요청 2개 제한

### 클라우드 LLM (Fallback): Google Gemini API
- **모델**: `gemini-2.5-flash` (Google AI Studio)
- **용도**: Ollama 서버 불가 시 뉴스 분류 대체 실행 (`scripts/run_gemini_classification.py`)
- **Rate Limit**: Free Tier 기준 15 RPM → 요청당 4.1초 딜레이 적용
- **API 키**: 환경변수 `GEMINI_API_KEY`로 관리 (프론트엔드 노출 금지)

### ML 모델: XGBoost
- **용도**: AI Quant 가격 예측 (Method A) — 유종별 독립 모델 6개 (7일/30일 × 3유종)
- **피처**: `feature_engineering.py`가 생성하는 시계열 피처 (이동평균, 변동률, 변동성, 유종 간 스프레드, 거시경제 지표, **KRW/USD 환율 및 환율 5일 변화율**)
- **저장**: `backend/ml/models/*.joblib`

---

## 패턴
- **프론트엔드**: 컴포넌트 기반 아키텍처. 재사용 컴포넌트는 `common/`에 분리
- **백엔드**: 레이어드 아키텍처 (API Route → Service → External/DB)
- **AI 통합**: 모든 Ollama(Gemma 4) 및 Gemini API 호출은 `backend/app/services/`에서만 수행
- **데이터 캐싱**: 외부 API 응답은 `backend/data/raw/`에 일별 캐시 (Rate Limit 대응)
- **벡터 DB**: ChromaDB (로컬 임베딩, 서버리스). 뉴스 + 유가 변동 매핑 데이터 + 시드 이벤트 적재
- **데이터베이스**: PostgreSQL (Docker 컨테이너, `asyncpg` 비동기 드라이버)
- **스케줄링**: APScheduler (`AsyncIOScheduler`)로 백그라운드 주기적 데이터 수집

## 데이터 흐름

```
[수집] Opinet(유가) / EIA(재고·생산) / FRED(거시) / NYT·Guardian(뉴스)
      → data_collector → data/raw/ (JSON 캐시) → PostgreSQL
                                                  ↓
[분류] raw news → news_classifier (Gemma 4, Ollama 로컬)
      → 6대 요인 + 유종별(Dubai/Brent/WTI) 독립 영향도 평가 (JSON)
      → PostgreSQL (classification_result 컬럼에 저장)
                                                  ↓
[적재] 분류된 뉴스 + 유종별 유가 변동률 → market_memory → ChromaDB
      (+ 과거 주요 사건 30건 시드 데이터 사전 적재)
                                                  ↓
[예측] Method A: feature_engineering → forecast_engine (XGBoost) → 유종별 6개 모델 추론
       Method B: fundamental_forecast (수급 기반 5대 시그널 가중 합산) → 유종별 전망
       ChromaDB 유사 사례 검색 (유종별 필터) → 유종별 News Adjustment% 산출 → 유종별 Final Band
                                                  ↓
[브리핑] 유종별 Final Band + 분류된 뉴스 → briefing_generator (Gemma 4)
         → 유종별 독립 전망 리포트 (일별 캐시 저장)
                                                  ↓
[표시] React Dashboard ← REST API ← FastAPI Route
       (USD/KRW 통화 토글: 한국수출입은행 환율 API 연동)
```

### 공공데이터 (data.go.kr) 통합 흐름
```
[CSV] 한국석유공사 원유수입 국가별 / 세계 원유 수출입 물량 (EUC-KR)
       → scripts/load_public_data.py → PostgreSQL (oil_imports / world_oil_trades)

[API] 한국수출입은행 환율 API (일별 매매기준율)
       → exchange_rate_collector → data/raw/ (JSON 캐시) + PostgreSQL (macro_indicators.krw_usd)
       → feature_engineering (krw_usd 피처) → XGBoost 학습
       → fundamental_forecast (달러 시그널 보조)
       → Frontend 환율 토글 (USD ↔ KRW 실시간 변환)

[분석] oil_imports → import_concentration (HHI 산출) → /api/public-data/import-concentration
```

## 자동화 파이프라인 (Scheduler)

```
APScheduler (AsyncIOScheduler, 기본 6시간 주기)
├── opinet_prices  → Opinet 유가 스크래핑
├── eia_inventory  → EIA 재고 데이터 API
├── eia_production → EIA 생산량 데이터 API
├── fred_macro     → FRED 거시경제 지표 API (최소 12시간 주기)
├── koreaexim_fx   → 한국수출입은행 환율 API (24시간 주기, 공공데이터 data.go.kr)
└── news_collect   → NYT + Guardian 뉴스 수집
                     → AI 분류 (news_classifier)
                     → 일일 브리핑 자동 생성 (briefing_generator)
```

- **즉시 수집**: 서버 시작 시 DB에 최신 데이터가 없으면 즉시 수집 트리거
- **수동 트리거**: Admin API를 통해 개별 소스 수동 수집 가능
- **간격 변경**: 런타임 중 스케줄 간격 동적 변경 지원 (1~24시간)

## 상태 관리 및 UX 최적화 아키텍처 (Frontend)
- **서버 상태 (Server State)**: React hooks (`useState`, `useEffect`)와 Fetch API를 결합하여 데이터 Fetching 관리.
  - *UX 최적화*: SWR / React-Query 패턴을 모방하여 데이터 캐시 및 **Pre-fetching 전략** 도입. 사용자의 마우스가 탭/메뉴에 닿는 시점(Hover)에 차트 데이터를 미리 불러와 빈 페이지 노출(Whiteout)을 방지.
- **클라이언트 상태 (Client State)**: 컴포넌트 종속적인 상태는 `useState`, `useReducer` 사용. 전역 상태 관리는 최소화.
  - `DashboardContext`: 날짜 범위, 선택된 카테고리 등 대시보드 전역 상태 관리.
- **글로벌 알림 센터 (Toast Provider)**: UI 플로우를 끊지 않고(Non-blocking), 백그라운드 데이터 갱신 완료, 간헐적 에러 발생 등의 정보를 사용자에게 부드럽게 전달하기 위해 React Context 기반의 전역 `ToastContext` 시스템 운용.

## 관리자 시스템 (Admin)

Admin 패널은 4개 섹션으로 구성:
- **Command Center**: DB 테이블별 레코드 수, 스케줄러 상태, Rate Limit 현황, 소스 건강도 모니터링
- **Pipeline**: 뉴스 AI 분류 현황 통계, 카테고리 분포, 분류 큐 관리, 재분류/오버라이드/보관함
- **Data Hub**: 과거 뉴스 대량 크롤링 (NYT + Guardian, 연도별 커버리지), 기사 검색/삭제/복구
- **Operations**: Gap Recovery (데이터 누락 진단 + 선택적 복구), 크롤링 이력 타임라인, 데이터 완결성 검증

## 외부 의존성

### Backend (Python)
| 패키지 | 용도 |
|--------|------|
| `fastapi`, `uvicorn` | 웹 프레임워크 |
| `xgboost`, `scikit-learn` | ML 모델 |
| `chromadb` | 벡터 DB (유사 사례 검색) |
| `pandas`, `numpy` | 데이터 처리 |
| `httpx` | 비동기 외부 API 호출 |
| `python-dotenv` | 환경변수 |
| `joblib` | 모델 직렬화 |
| `apscheduler` | 백그라운드 스케줄러 |
| `pydantic-settings` | 설정 관리 및 Validation |
| `sqlalchemy[asyncio]`, `asyncpg` | PostgreSQL 비동기 ORM |
| `google-generativeai` | Gemini API 클라이언트 (Fallback LLM) |
| `beautifulsoup4`, `lxml` | 웹 스크래핑 (Opinet, 뉴스 크롤링) |

### Frontend (npm)
| 패키지 | 용도 |
|--------|------|
| `lightweight-charts` | 차트 라이브러리 (캔들스틱) |

### Infrastructure
| 구성 요소 | 설명 |
|-----------|------|
| PostgreSQL 16 (Docker) | 운영 데이터베이스 (`docker-compose.yml`) |
| Ollama | 로컬 LLM 서버 (Gemma 4 호스팅) |
| ChromaDB | 벡터 DB (임베딩 기반 유사 사례 검색, 서버리스) |

### 외부 API 소스
| API | 용도 | Rate Limit |
|-----|------|------------|
| Opinet (한국석유공사) | Dubai/Brent/WTI 일별 유가 | 제한 없음 (스크래핑) |
| EIA (미국 에너지정보청) | 원유 재고, 생산량 | 무제한 (초당 1건 권장) |
| FRED (미국 연준) | 금리, 달러 인덱스 | 무제한 (합리적 사용) |
| NYT (뉴욕타임스) | 원유 관련 뉴스 | 500회/일 |
| The Guardian | 원유 관련 뉴스 | 5,000회/일 |
| 한국수출입은행 (data.go.kr) | KRW/USD 매매기준율 (일별) | 1,000회/일 |
| 한국석유공사 KNOC (data.go.kr) | 원유수입 국가별 / 세계 수출입 물량 (CSV) | 파일 다운로드 |
