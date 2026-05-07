# Architecture Decision Records (ADR)

## 철학
MVP 속도 최우선. 무료/오픈 데이터 소스 우선 활용. 작동하는 최소 구현을 선택하되, 확장 가능한 구조를 유지한다. 단, 엔터프라이즈 환경에서의 안정성 확보를 위해 치명적 에러 및 외부 의존성(Third-Party) 장애에 대한 **회복 탄력성(Resilience)**은 타협하지 않는다.

---

### ADR-001: React + Vite 선택
**결정**: 프론트엔드 프레임워크로 React + Vite + TypeScript를 선택
**이유**: 빠른 HMR, 간결한 설정, TypeScript 네이티브 지원. 금융 차트 라이브러리 생태계가 풍부함.
**트레이드오프**: SSR이 필요하면 Next.js로 마이그레이션 필요

### ADR-002: FastAPI 선택
**결정**: 백엔드 프레임워크로 FastAPI를 선택
**이유**: Python ML 생태계(XGBoost, scikit-learn, pandas)와의 자연스러운 통합. async 지원으로 다수 외부 API 병렬 호출에 유리. 자동 API 문서(Swagger).
**트레이드오프**: Node.js 대비 프론트엔드와 언어 통일 불가

### ADR-003: Gemma 4 API (생성형 AI) - [Superseded by ADR-012]
**결정**: AI 서비스로 Gemma 4 모델을 선택
**이유**: 뛰어난 범용성, 한국어 처리 능력, 긴 컨텍스트 윈도우로 뉴스 분석에 적합
**트레이드오프**: 최적화 및 튜닝 시간이 일부 소요될 수 있음
**비고**: ADR-012 결정에 따라 클라우드 API 호출 방식에서 로컬 Docker 호스팅(Ollama) 방식으로 전환됨.

### ADR-004: ChromaDB (벡터 DB)
**결정**: 벡터 DB로 ChromaDB를 선택
**이유**: Python 네이티브, 서버리스(임베디드 모드), 별도 인프라 불필요. MVP에서 빠르게 시작 가능.
**트레이드오프**: 대규모 프로덕션에서는 Pinecone/Weaviate로 마이그레이션 고려 필요

### ADR-005: XGBoost (시계열 예측)
**결정**: 정량적 유가 예측 모델로 XGBoost를 선택
**이유**: 테이블형 시계열 피처에 강점. Prophet 대비 커스텀 피처 엔지니어링 유연. 학습/추론 속도 빠름.
**트레이드오프**: 딥러닝(LSTM, Transformer) 대비 장기 패턴 포착 한계. 성능 검증 후 모델 교체 가능하도록 인터페이스 분리.

### ADR-006: 유가 데이터 소스 이원화 — Opinet(유가) + EIA(수급) [Updated]
**결정**: 국제 유가(Dubai/Brent/WTI)는 한국석유공사 오피넷 웹 스크래핑으로, 재고·생산량 데이터는 EIA API v2로 수집.
**이유**: 오피넷은 Dubai유 포함 3유종 USD 일별 가격을 무료로 제공하며, 한국 시장 기준 공식 가격에 가장 가깝다. EIA는 Dubai유 데이터가 없어 유가 소스로는 부적합하나, 미국 원유 재고(WCESTUS1)와 생산량(WCRFPUS2) 주간 데이터는 EIA가 유일한 무료 공신력 소스.
**트레이드오프**: 오피넷은 공식 API가 아닌 HTML 스크래핑(`BeautifulSoup`)이므로 사이트 구조 변경 시 파서 수정 필요. `opinet_collector.py`에서 POST form-data로 조회 후 `tbody2`(USD 테이블)를 파싱하는 방식.

### ADR-007: GDELT 대신 NYT + Guardian으로 뉴스 소스 전환 [Superseded]
**초기 결정**: 과거 지정학 이벤트-유가 매핑에 GDELT를 활용
**전환 결정**: 실시간 뉴스 소스를 NYT Article Search API + The Guardian Open Platform API로 변경.
**전환 이유**: GDELT는 과거 이벤트 DB로는 우수하나 실시간 뉴스 수집에는 지연이 크고, BigQuery 설정이 MVP에 과도한 오버헤드. NYT와 Guardian은 원유 관련 영문 기사 품질이 높고, 무료 티어(NYT 500회/일, Guardian 5,000회/일)가 충분.
**트레이드오프**: 과거 사례 매핑은 `historical_loader.py`의 시드 데이터(주요 유가 사건 30건)로 대체. 향후 GDELT 연동은 `backfill_from_gdelt()` 메서드로 확장 가능하도록 인터페이스만 남겨둠.

### ADR-008: 하이브리드 추정 전략
**결정**: 정량 모델(XGBoost) + 정성 보정(Gemma 4 뉴스 분석)의 하이브리드 방식 채택
**이유**: 순수 시계열 모델은 블랙스완(지정학 이벤트)에 취약. 뉴스 기반 보정으로 설명 가능성(Explainability)과 적시성을 확보.
**트레이드오프**: 뉴스 분석의 정확도가 전체 추정 품질에 영향. 보정 가중치 튜닝 필요.

---

## 🛡️ 예외 처리 및 회복 탄력성 (Resilience) 결정을 위한 추가 기록

### ADR-009: 외부 Third-Party 장애 대비 스태틱 캐시(Static Cache) Fallback 운용
**결정**: 외부 데이터 프로바이더(EIA, FRED, NewsAPI 등) 장애 및 Rate Limits 발생 시 즉시 서버 에러를 표출하지 않고, 로컬 저장소(`data/raw`)에 스냅샷 형태로 남은 가장 최근 캐시를 Fallback 데이터로 적극 사용.
**이유**: API 연동 에러가 사용자 경험 저해(단순 시스템 먹통)로 직결되는 것을 방지. 비즈니스 목적 상 지난 주/어제 데이터만 보여주어도 일정 수준의 의사결정에 도움이 됨.
**트레이드오프**: 실시간성이 떨어지는 데이터(Stale Data)를 볼 위험이 있으므로, Fallback이 동작할 경우 프론트엔드 UI에 명시적인 `지연(Delayed) 안내 뱃지`를 구현해야 함.

### ADR-010: LLM 예측/분석 의존성에 대한 서킷 브레이커 도입
**결정**: Gemma 4 API 호출 실패(Token Limit, 타임아웃 15초 초과 등) 시, 일정 재시도(Recur 3회) 후 강제로 AI 모듈을 비활성화(Circuit Open) 시킴.
**이유**: LLM 응답을 무한 대기하다가 시스템 리소스 전체가 고갈되는 현상을 방지. AI 분석이 없더라도 Baseline 모델과 차트는 정상 동작해야 함(Graceful Degradation).
**트레이드오프**: 일시적으로 단순 통계치만 출력될 수 있음.

### ADR-011: 클라이언트 단의 국소적 장애(Partial Error) 전략
**결정**: 컴포넌트 단위 React `ErrorBoundary`를 주요 위젯(AI 브리핑 창, 뉴스 익스플로러 등)에 씌워 부분적 위젯 마비가 메인 대시보드 강제 크래시로 번지는 것을 차단.
**이유**: 복합 대시보드의 특성상 특정 섹션이 오작동해도 메인 차트 등 다른 섹션은 계속 모니터링이 가능해야 함.
**트레이드오프**: 에러 처리 코드 보일러플레이트가 증가함.

### ADR-012: 로컬 Native 기반 Gemma 4 전환 (분석망의 진화)
**결정**: Homebrew로 설치되는 Ollama Native App(데몬)을 사용하여 로컬 환경에 Gemma 4 모델을 직접 호스팅하고 HTTP로 연동. (ADR-003 및 이전 Docker 계획에서 최종 변경)
**이유**: 완전한 오프라인 운영과 더불어 Apple Silicon(Metal) 자원을 한 치의 낭비 없는 100% 효율로 사용하기 위함.
**트레이드오프**: 환경을 맞추기 위한 초기 Homebrew/앱 설치의 번거로움이 존재함. 그러나 일단 설정되면 압도적으로 빠른 생성 속도를 보장함.

### ADR-013: 유종별(Crude-Type-Specific) 독립 분석 전략
**결정**: 뉴스 분류, 벡터 DB 검색, XGBoost 예측, 브리핑 생성의 전체 파이프라인을 두바이유, 브렌트유, WTI 각각에 대해 독립적으로 수행하도록 설계.
**이유**: 유종마다 영향을 받는 지정학적 요인과 지역적 배경이 근본적으로 다름. (예: 호르무즈 해협 이슈는 두바이유에 직격탄이지만 WTI에는 간접 영향만 미침) 단일 모델로는 이 차이를 포착할 수 없으며, 정확한 예측을 위해 유종별 독립 파이프라인이 필수적.
**구현 범위**:
  - `NewsClassifier`: 기사당 `impact_by_crude` (Dubai/Brent/WTI 개별 score/direction/rationale) 산출
  - `MarketMemory`: 유종별 메타데이터 저장 + `crude_type` 필터 검색
  - `ForecastEngine`: 6개 XGBoost 모델 (3유종 × 2시계)
  - `NewsAdjuster`: 유종별 독립 보정값 산출
  - `BriefingGenerator`: `crude_outlooks` 유종별 독립 전망
**트레이드오프**: 모델 학습 시간 3배 증가, 프롬프트 토큰 사용량 증가. 그러나 예측 정확도와 설명 가능성 측면에서 획기적인 개선. 향후 pgvector 마이그레이션 시 유종별 가중치 필터링이 더욱 정교해질 수 있음.

### ADR-014: SQLite에서 PostgreSQL로 데이터베이스 전환
**결정**: 운영 데이터베이스를 SQLite에서 PostgreSQL 16 (Docker 컨테이너)으로 전환.
**이유**: SQLite는 동시 쓰기 제한(WAL 모드에서도 단일 Writer)으로 APScheduler + 실시간 API 요청이 충돌. JSON 컬럼 쿼리(`classification_result->>'category'` 등)에 PostgreSQL의 JSONB 연산자가 필수적.
**구현**: `docker-compose.yml`로 PostgreSQL 16-alpine 컨테이너 운영. `SQLAlchemy[asyncio]` + `asyncpg` 비동기 드라이버. 마이그레이션은 `scripts/migrate_sqlite_to_pg.py`로 일회성 수행.
**트레이드오프**: 로컬 개발 시 Docker 필수. 단, `docker-compose up -d` 한 줄로 시작 가능하므로 허용 범위.

### ADR-015: NYT + Guardian을 뉴스 수집 소스로 확정
**결정**: 실시간 뉴스 수집 소스를 New York Times Article Search API와 The Guardian Open Platform API로 확정.
**이유**: 원유 시장 관련 영문 기사의 품질과 커버리지가 우수. 두 소스 모두 무료 티어가 충분(NYT 500회/일, Guardian 5,000회/일). URL 기반 중복 제거(`SHA256 해시`)로 두 소스 간 중복 방지.
**트레이드오프**: NewsAPI(100회/일), GNews(100회/일)는 할당량이 부족하여 제외. GDELT는 실시간성이 낮아 제외.

### ADR-016: Gemini API를 클라우드 Fallback LLM으로 추가
**결정**: Ollama(Gemma 4) 로컬 LLM이 불가능한 환경에서 Google Gemini API(`gemini-2.5-flash`)를 Fallback으로 사용.
**이유**: Ollama 서버가 다운되거나 Apple Silicon이 없는 환경에서도 뉴스 분류를 수행할 수 있어야 함. `scripts/run_gemini_classification.py`로 수동 실행.
**트레이드오프**: Free Tier 기준 15 RPM으로 대량 분류 시 느림(요청당 4.1초 딜레이). API 키(`GEMINI_API_KEY`)를 환경변수로 관리하며 프론트엔드에 절대 노출 금지.

### ADR-017: 듀얼 예측 전략 — AI Quant (Method A) + 펀더멘탈 (Method B)
**결정**: XGBoost 기반 가격 파생 패턴 인식(Method A)과 수급 기반 펀더멘탈 분석(Method B)을 병행하는 듀얼 예측 전략 채택.
**이유**: Method A는 가격 파생 지표(이동평균, 변동성 등)로 단기 패턴을 포착하지만, 실물 시장(재고, 생산, 계절성) 변화를 반영하지 못함. Method B(EIA STEO 방법론 참고)는 5대 시그널(재고 변화, 생산량 추세, 계절 패턴, 평균 회귀, 달러 영향)을 신뢰도 기반 가중 합산하여 독립적인 전망을 산출.
**구현**: `forecast_engine.py`(Method A) + `fundamental_forecast.py`(Method B). 프론트엔드 `ForecastComparison` 테이블에서 두 결과를 나란히 표시.
**트레이드오프**: 두 방법론의 결과가 상충할 경우 사용자가 직접 판단해야 함. 자동 앙상블은 MVP 이후 과제.

### ADR-018: APScheduler 기반 데이터 수집 자동화
**결정**: APScheduler(`AsyncIOScheduler`)를 사용하여 백그라운드 데이터 수집을 자동화.
**이유**: FastAPI의 lifespan 이벤트와 자연스럽게 통합. 기본 6시간 주기로 유가/재고/생산/거시/뉴스를 순차 수집하고, 뉴스 수집 후 AI 분류 → 일일 브리핑 자동 생성까지 파이프라인으로 연결.
**구현**: Singleton 패턴(`CollectionScheduler`). 서버 시작 시 DB 최신 데이터 확인 → 누락 시 즉시 수집. 런타임 중 스케줄 간격 동적 변경(1~24시간) 지원. 각 작업 결과는 `collection_logs` 테이블에 기록.
**트레이드오프**: 단일 프로세스 내 스케줄러이므로 서버 재시작 시 상태 소실. Celery/Redis 도입은 MVP 이후 과제.

