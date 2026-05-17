# Changelog

이 프로젝트의 모든 주요 변경 사항을 기록합니다.
형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/)를 따릅니다.

## [Unreleased]
- docs: NotebookLM 05_ML_FEATURES 전면 재작성 — 유종별 독립 피처, 크로스 스프레드, 래깅 피처, 피처 총 수 테이블 반영
- docs: NotebookLM 01_PRD + docs/PRD.md 엣지 케이스 테이블 뉴스 소스 명칭 수정 (NewsAPI/GNews → NYT/Guardian)
- docs: NotebookLM 08_기술구현_상세 파일 크기/서비스 설명 실제 코드베이스와 동기화 + 헬스체크 엔드포인트 보충

## [0.3.0] - 2026-05-10

### Added
- feat: 한국수출입은행 환율 API 연동 — 원/달러 매매기준율 자동 수집 (공공데이터 data.go.kr)
- feat: 한국석유공사 원유수입 국가별 CSV 적재 — 수입 집중도(HHI) 분석 서비스
- feat: 한국석유공사 세계 원유 수출입 물량 CSV 적재 — 글로벌 교역 흐름 분석
- feat: 공공데이터 전용 API 라우터 (`/api/public-data/`) — 환율, 수입집중도, 데이터소스 메타
- feat: 대시보드 USD/KRW 통화 토글 — 원화 기준 유가 실시간 표시
- feat: 예측 모델 피처 확장 — krw_usd, krw_usd_change_5d 거시경제 피처 추가
- feat: 펀더멘탈 예측 달러 시그널에 원/달러 환율 보조 정보 추가

### Changed
- docs: 프로젝트 공식 명칭 Petro-AX → OilLens 통일 (GEMINI.md, PRD.md, UI_GUIDE.md, FEATURES.md, config.py)

### Fixed
- fix: 수동 브리핑 재생성 API(`POST /api/briefing/generate`) 및 스케줄러 자동 생성 시 발생하는 500 에러(언패킹 버그) 통합 수정

### Docs
- docs: OilLens 아키텍처 다이어그램 재생성 — 현재 서비스/컴포넌트 구조 반영
- docs: 서비스 아키텍처 다이어그램 재생성 (`docs/architecture_diagram.png`)
- docs: 피그마 스타일 아키텍처 다이어그램 추가 (`docs/architecture_diagram_figma.png`)
- docs: ARCHITECTURE.md, ADR.md, PRD.md 공공데이터 통합 반영 동기화

## [0.2.0] - 2026-05-07

### Added
- feat: 듀얼 예측 엔진 — AI Quant (XGBoost, Method A) + 펀더멘탈 수급 분석 (Method B) 병행 표시
- feat: 펀더멘탈 예측 엔진 (`fundamental_forecast.py`) — 5대 시그널 가중 합산 기반 유종별 7일 전망
- feat: Admin Command Center — DB 상태, 스케줄러, Rate Limit, 소스 건강도 실시간 모니터링
- feat: Admin Pipeline — 뉴스 AI 분류 현황, 카테고리 분포, 재분류/오버라이드/보관함
- feat: Admin Data Hub — 과거 뉴스 대량 크롤링 (NYT + Guardian, 연도별 커버리지)
- feat: Admin Operations — Gap Recovery (데이터 누락 진단 + 선택적 복구)
- feat: APScheduler 기반 자동 수집 파이프라인 (유가/재고/생산/거시/뉴스 → AI 분류 → 브리핑)
- feat: Gemini API (`gemini-2.5-flash`) Fallback 분류 스크립트 추가
- feat: 과거 뉴스 아카이브 크롤러 (`archive_crawler.py`, OilPrice.com)
- feat: ChromaDB 시드 데이터 로더 — 주요 유가 사건 30건 사전 적재
- feat: Rate Limit 중앙 관리 엔진 (`rate_limiter.py`) — API별 일일 한도 + Exponential Backoff
- feat: Gap Recovery 서비스 (`gap_recovery.py`) — 소스별 누락 진단 및 복구

### Changed
- refactor: 데이터베이스 SQLite → PostgreSQL 16 (Docker) 전환
- refactor: 뉴스 소스 NewsAPI/GNews → NYT + Guardian 전환
- refactor: 유가 소스 이원화 — Opinet(유가 스크래핑) + EIA(재고/생산)
- refactor: Gemma 4 호스팅 — 클라우드 API → Ollama 로컬 Native 전환

### Docs
- docs: ARCHITECTURE.md 전면 재작성 — 실제 코드베이스 기준 동기화
- docs: ADR.md — ADR-006/007 업데이트, ADR-014~018 추가 (PostgreSQL, NYT/Guardian, Gemini Fallback, 듀얼 예측, APScheduler)
- docs: PRD.md — 데이터 소스 테이블, 예측 엔진 로직, Method B 추가 반영

## [0.1.0] - 2026-04-28

### Added
- feat: 메인 대시보드 (유가 차트, 뉴스 익스플로러, AI 브리핑, 6대 요인 게이지)
- feat: XGBoost 기반 유종별 독립 예측 엔진 (Method A)
- feat: Gemma 4 뉴스 6대 요인 분류기 + 유종별 영향도 평가
- feat: AI 일일 브리핑 자동 생성기
- feat: ChromaDB 벡터 검색 (유사 과거 사례 탐색)
- feat: 유가 데이터 수집기 (Opinet, EIA, FRED)
- feat: React + TypeScript 프론트엔드 (Vite)
- feat: FastAPI 백엔드
