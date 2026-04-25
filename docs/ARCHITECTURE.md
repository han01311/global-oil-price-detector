# 아키텍처

## 디렉토리 구조
```
global-oil-price-detector/
├── frontend/                    # React + TypeScript (Vite)
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard/       # 메인 대시보드 레이아웃
│   │   │   ├── PriceChart/      # 유가 차트 (캔들스틱 + 밴드)
│   │   │   ├── NewsExplorer/    # 뉴스 익스플로러 & 필터
│   │   │   ├── Briefing/        # AI 브리핑 뷰어
│   │   │   ├── FactorGauge/     # 6대 요인 게이지/레이더
│   │   │   └── common/          # 공통 UI (ErrorBoundary, Badge, Card, Skeleton 등)
│   │   ├── types/               # TypeScript 타입 정의
│   │   ├── hooks/               # Custom hooks
│   │   ├── services/            # API 호출 래퍼 (백엔드만 호출)
│   │   ├── utils/               # 유틸리티 함수 (에러 로거나 파서 등)
│   │   ├── App.tsx              # 루트 컴포넌트
│   │   └── main.tsx             # 엔트리 포인트
│   └── public/                  # 정적 파일
│
├── backend/                     # FastAPI (Python)
│   ├── app/
│   │   ├── api/                 # API 라우트 핸들러 (Presentation)
│   │   │   ├── prices.py        # 유가 데이터 엔드포인트
│   │   │   ├── news.py          # 뉴스 분류/검색 엔드포인트
│   │   │   ├── forecast.py      # 추정 엔진 엔드포인트
│   │   │   └── briefing.py      # AI 브리핑 엔드포인트
│   │   ├── core/                # 설정, 보안, 미들웨어, 글로벌 에러 래퍼
│   │   │   ├── config.py        # 환경변수, API 키 관리
│   │   │   └── exceptions.py    # 글로벌 Exception 핸들러 및 규격
│   │   ├── models/              # DB 모델
│   │   ├── schemas/             # Pydantic 스키마 (데이터 Validation)
│   │   │   ├── price.py         # 유가 데이터 스키마
│   │   │   ├── news.py          # 뉴스/요인 분류 스키마
│   │   │   └── forecast.py      # 추정 결과 스키마
│   │   ├── services/            # 비즈니스 로직 + AI 서비스
│   │   │   ├── data_collector.py    # 외부 API 데이터 수집기
│   │   │   ├── news_classifier.py   # Gemma 4 뉴스 요인 분류기
│   │   │   ├── forecast_engine.py   # XGBoost 추정 엔진
│   │   │   ├── market_memory.py     # ChromaDB 벡터 검색
│   │   │   └── briefing_generator.py # AI 브리핑 생성기
│   │   └── main.py              # FastAPI 앱 인스턴스
│   ├── data/                    # 로컬 데이터 캐시 (Fallback 스토리지)
│   │   ├── raw/                 # 원시 API 응답 캐시
│   │   └── processed/           # 전처리된 학습 데이터
│   ├── ml/                      # ML 모델 아티팩트
│   │   └── models/              # 학습된 모델 파일 (.joblib)
│   └── tests/                   # pytest 테스트
│
├── docs/                        # 프로젝트 문서
├── scripts/                     # 하네스 스크립트
├── phases/                      # 하네스 phase 디렉토리
└── GEMINI.md                    # 프로젝트 규칙
```

## 핵심 서비스 API 아키텍처

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React)                  │
│ [ErrorBoundary] Dashboard │ PriceChart │ Briefing    │
└──────────────────────┬──────────────────────────────┘
                       │ fetch (REST /w Timeout & Retry)
┌──────────────────────▼──────────────────────────────┐
│                 Backend (FastAPI)                     │
│  ┌────────────────────────────────────────────────┐   │
│  │ Exception Middleware (Global Error Handler)    │   │
│  └───────────────────┬────────────────────────────┘   │
│  ┌─────────┐  ┌──────▼───┐  ┌──────────┐  ┌──────┐    │
│  │ prices  │  │   news   │  │ forecast │  │brief-│    │
│  │  .py    │  │   .py    │  │   .py    │  │ing   │    │
│  └────┬────┘  └────┬─────┘  └────┬─────┘  └──┬───┘    │
│       │            │             │             │      │
│  ┌────▼────────────▼─────────────▼─────────────▼───┐  │
│  │              Service Layer                       │  │
│  │ data_collector │ news_classifier │ forecast_eng  │  │
│  │ market_memory  │ briefing_generator              │  │
│  └─────┬───────────┬────────────┬──────────────┬───┘  │
│        │ [Fallback/Cache Storage Integration]  │      │
└────────┼───────────┼────────────┼──────────────┼──────┘
         │           │            │              │
    ┌────▼───┐  ┌────▼────┐  ┌───▼───┐   ┌─────▼─────┐
    │External│  │ Ollama  │  │XGBoost│   │ ChromaDB  │
    │APIs    │  │(Gemma 4)│  │Model  │   │ (Vector)  │
    │EIA,FRED│  │         │  │       │   │           │
    └────────┘  └─────────┘  └───────┘   └───────────┘
```

---

## 🛡️ 시스템 에러 핸들링 및 회복탄력성 (Resilience) 계층

시스템이 외부에 크게 의존하고 있기 때문에 API Rate Limit, 외부 서비스 다운, 예측 모델 오류에 대응하는 **회복탄력성 파이프라인**을 갖춥니다.

### 1. 외부 API 통신: Circuit Breaker 및 캐시 Fallback
- `data_collector.py` 는 EIA, FRED, NewsAPI 등을 주기적으로 호출합니다.
- **Fail-over**: 장애나 Rate Limit 발생 시 즉시 오류 처리하지 않고, 백엔트 로컬의 최신 캐시(`backend/data/raw/`) 데이터를 자동으로 로드해 제공합니다. (Stale Data Serving 전략)
- **Exponential Backoff**: 써드파티 API 실패 시, 재요청 주기(Retry Delay)를 지수적으로 증가시키며 재시도 하도록 데코레이터(`tenacity` 등)를 적용합니다.

### 2. 데이터 무결성 검증 (Data Validation) 파이프라인
머신러닝과 LLM에 오염된 데이터가 주입되어 크래시되는 현상을 막기 위해 강력한 검증 단계를 거칩니다.
- **Pydantic 스키마 검증**: 모든 들어오고 나가는 데이터는 Pydantic 스키마(`schemas/*.py`) 레이어를 통과합니다. 누락된 키, Null 값, 비정상적인 유가(예: 음수 가격) 등이 탐지되면 즉각 예외(`ValidationError`)를 던져 잘못된 모델 학습을 차단합니다.
- **LLM 응답 검증 (JSON Parsing Fallback)**: Gemma 4 API가 할루시네이션으로 인해 깨진 JSON을 내뱉을 경우, 백엔드 로직 선에서 정규식 혹은 재시도를 통해 보정합니다. 회복 불가능할 시 해당 뉴스는 `[Unknown Category]`로 안전하게 드롭(Drop)시킵니다.

### 3. 글로벌 에러 전파 원칙 (Error Propagation Flow)
- **백엔드**: 비즈니스 로직(Service Layer)에서 발생한 에러는 구체적 원인 파악을 위해 고유 에러 코드와 함께 패키징되어 FastAPI의 글로벌 예외 핸들러(`Exception Middleware`)에서 포착됩니다. 클라이언트에게는 보안에 민감한 스택 트리거를 은폐하고 표준화된 `{ "code": "E1001", "message": "...", "retryable": true }` 형태의 HTTP 500 / 503 에러로 변환해 전달합니다.
- **프론트엔드**: 서비스 레벨에서 컴포넌트별로 `React ErrorBoundary`를 배치합니다. 
  - 특정 모듈(예: 뉴스 익스플로러)에 렌더링/데이터 오류 발생 시 대시보드 전체가 깨지지 않도록 해당 영역만 Fallback UI (Error State) 전환 처리.

---

## 패턴
- **프론트엔드**: 컴포넌트 기반 아키텍처. 재사용 컴포넌트는 `common/`에 분리
- **백엔드**: 레이어드 아키텍처 (API Route → Service → External)
- **AI 통합**: 모든 Ollama(Gemma 4) 호출은 `backend/app/services/`에서만 수행
- **데이터 캐싱**: 외부 API 응답은 `backend/data/raw/`에 일별 캐시 (rate limit 대응)
- **벡터 DB**: ChromaDB (로컬 임베딩, 서버리스). 뉴스 + 유가변동 매핑 데이터 적재

## 데이터 흐름

```
[수집] EIA/FRED/News API → data_collector → data/raw/ (JSON 캐시)
                                          ↓
[분류] raw news → news_classifier (Gemma 4) → 6대 요인 + Impact Score (JSON)
                                            ↓
[적재] 분류된 뉴스 + 당시 유가 변동률 → market_memory → ChromaDB
                                                        ↓
[예측] data/processed → forecast_engine (XGBoost) → Baseline
       ChromaDB 유사 사례 → News Adjustment% → Final Band
                                                ↓
[브리핑] Final Band + 유사 사례 → briefing_generator (Gemma 4) → 리포트
                                                               ↓
[표시] React Dashboard ← REST API ← FastAPI Route (에러 포맷팅 거쳐 서빙)
```

## 상태 관리 및 UX 최적화 아키텍처 (Frontend)
- **서버 상태 (Server State)**: React hooks (`useState`, `useEffect`)와 Fetch API를 결합하여 데이터 Fetching 관리. 
  - *UX 최적화*: SWR / React-Query 패턴을 모방하여 데이터 캐시 및 **Pre-fetching 전략** 도입. 사용자의 마우스가 탭/메뉴에 닿는 시점(Hover)에 차트 데이터를 미리 불러와 빈 페이지 노출(Whiteout)을 방지.
- **클라이언트 상태 (Client State)**: 컴포넌트 종속적인 상태는 `useState`, `useReducer` 사용. 전역 상태 관리는 최소화.
- **글로벌 알림 센터 (Toast Provider)**: UI 플로우를 끊지 않고(Non-blocking), 백그라운드 데이터 갱신 완료, 간헐적 에러 발생 등의 정보를 사용자에게 부드럽게 전달하기 위해 React Context 기반의 전역 `Toast/Notification 시스템` 운용.

## 외부 의존성

### Backend (Python)
| 패키지 | 용도 |
|--------|------|
| `fastapi`, `uvicorn` | 웹 프레임워크 |
| `xgboost`, `scikit-learn` | ML 모델 |
| `chromadb` | 벡터 DB |
| `pandas`, `numpy` | 데이터 처리 |
| `httpx` | 비동기 외부 API 호출 |
| `python-dotenv` | 환경변수 |
| `joblib` | 모델 직렬화 |
| `tenacity` | 재시도 및 백오프 로직 구현 (추천) |

### Frontend (npm)
| 패키지 | 용도 |
|--------|------|
| `recharts` 또는 `lightweight-charts` | 차트 라이브러리 |
| `react-router-dom` | 라우팅 (필요시) |
