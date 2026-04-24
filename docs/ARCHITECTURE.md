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
│   │   │   └── common/          # 공통 UI (Badge, Card, Skeleton 등)
│   │   ├── types/               # TypeScript 타입 정의
│   │   ├── hooks/               # Custom hooks
│   │   ├── services/            # API 호출 래퍼 (백엔드만 호출)
│   │   ├── utils/               # 유틸리티 함수
│   │   ├── App.tsx              # 루트 컴포넌트
│   │   └── main.tsx             # 엔트리 포인트
│   └── public/                  # 정적 파일
│
├── backend/                     # FastAPI (Python)
│   ├── app/
│   │   ├── api/                 # API 라우트 핸들러
│   │   │   ├── prices.py        # 유가 데이터 엔드포인트
│   │   │   ├── news.py          # 뉴스 분류/검색 엔드포인트
│   │   │   ├── forecast.py      # 추정 엔진 엔드포인트
│   │   │   └── briefing.py      # AI 브리핑 엔드포인트
│   │   ├── core/                # 설정, 보안, 미들웨어
│   │   │   └── config.py        # 환경변수, API 키 관리
│   │   ├── models/              # DB 모델
│   │   ├── schemas/             # Pydantic 스키마
│   │   │   ├── price.py         # 유가 데이터 스키마
│   │   │   ├── news.py          # 뉴스/요인 분류 스키마
│   │   │   └── forecast.py      # 추정 결과 스키마
│   │   ├── services/            # 비즈니스 로직 + AI 서비스
│   │   │   ├── data_collector.py    # 외부 API 데이터 수집기
│   │   │   ├── news_classifier.py   # Gemini 뉴스 요인 분류기
│   │   │   ├── forecast_engine.py   # XGBoost 추정 엔진
│   │   │   ├── market_memory.py     # ChromaDB 벡터 검색
│   │   │   └── briefing_generator.py # AI 브리핑 생성기
│   │   └── main.py              # FastAPI 앱 인스턴스
│   ├── data/                    # 로컬 데이터 캐시
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

## 핵심 서비스 아키텍처

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React)                  │
│  Dashboard │ PriceChart │ NewsExplorer │ Briefing    │
└──────────────────────┬──────────────────────────────┘
                       │ fetch (REST API)
┌──────────────────────▼──────────────────────────────┐
│                 Backend (FastAPI)                     │
│                                                      │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────┐ │
│  │ prices  │  │   news   │  │ forecast │  │brief-│ │
│  │  .py    │  │   .py    │  │   .py    │  │ing   │ │
│  └────┬────┘  └────┬─────┘  └────┬─────┘  └──┬───┘ │
│       │            │             │             │      │
│  ┌────▼────────────▼─────────────▼─────────────▼───┐ │
│  │              Service Layer                       │ │
│  │  data_collector │ news_classifier │ forecast_eng │ │
│  │  market_memory  │ briefing_generator             │ │
│  └─────┬───────────┬────────────┬──────────────┬───┘ │
└────────┼───────────┼────────────┼──────────────┼─────┘
         │           │            │              │
    ┌────▼───┐  ┌────▼────┐  ┌───▼───┐   ┌─────▼─────┐
    │External│  │ Gemini  │  │XGBoost│   │ ChromaDB  │
    │APIs    │  │ API     │  │Model  │   │ (Vector)  │
    │EIA,FRED│  │         │  │       │   │           │
    │News,WB │  │         │  │       │   │           │
    └────────┘  └─────────┘  └───────┘   └───────────┘
```

## 패턴
- **프론트엔드**: 컴포넌트 기반 아키텍처. 재사용 컴포넌트는 `common/`에 분리
- **백엔드**: 레이어드 아키텍처 (API Route → Service → External)
- **AI 통합**: 모든 Gemini API 호출은 `backend/app/services/`에서만 수행
- **데이터 캐싱**: 외부 API 응답은 `backend/data/raw/`에 일별 캐시 (rate limit 대응)
- **벡터 DB**: ChromaDB (로컬 임베딩, 서버리스). 뉴스 + 유가변동 매핑 데이터 적재

## 데이터 흐름

```
[수집] EIA/FRED/News API → data_collector → data/raw/ (JSON 캐시)
                                          ↓
[분류] raw news → news_classifier (Gemini) → 6대 요인 + Impact Score (JSON)
                                            ↓
[적재] 분류된 뉴스 + 당시 유가 변동률 → market_memory → ChromaDB
                                                        ↓
[예측] data/processed → forecast_engine (XGBoost) → Baseline
       ChromaDB 유사 사례 → News Adjustment% → Final Band
                                                ↓
[브리핑] Final Band + 유사 사례 → briefing_generator (Gemini) → 리포트
                                                               ↓
[표시] React Dashboard ← REST API ← FastAPI Route
```

## 상태 관리
- 서버 상태: React hooks (useState, useEffect) + API 호출
- 클라이언트 상태: useState / useReducer
- 필요시 Context API 사용 (전역 상태 최소화)

## 외부 의존성

### Backend (Python)
| 패키지 | 용도 |
|--------|------|
| `fastapi`, `uvicorn` | 웹 프레임워크 |
| `google-generativeai` | Gemini API |
| `xgboost`, `scikit-learn` | ML 모델 |
| `chromadb` | 벡터 DB |
| `pandas`, `numpy` | 데이터 처리 |
| `httpx` | 비동기 외부 API 호출 |
| `python-dotenv` | 환경변수 |
| `joblib` | 모델 직렬화 |

### Frontend (npm)
| 패키지 | 용도 |
|--------|------|
| `recharts` 또는 `lightweight-charts` | 차트 라이브러리 |
| `react-router-dom` | 라우팅 (필요시) |
