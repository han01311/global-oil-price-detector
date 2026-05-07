# 프로젝트: Petro-AX (글로벌 유가 추정 대시보드)

## 기술 스택
- Frontend: React + TypeScript (Vite)
- Backend: FastAPI (Python)
- AI: Ollama (Gemma 4 로컬) + Google Gemini API (Fallback)
- 스타일링: Vanilla CSS

## 아키텍처 규칙
- CRITICAL: 프론트엔드에서 직접 외부 API를 호출하지 말 것. 반드시 백엔드 API를 통해 호출할 것
- CRITICAL: 모든 AI 관련 로직은 backend/app/services/ 에서만 처리할 것
- CRITICAL: 환경 변수(API 키 등)는 절대 프론트엔드에 노출하지 말 것
- 프론트엔드 컴포넌트는 frontend/src/components/ 폴더에, 타입은 frontend/src/types/ 폴더에 분리
- 백엔드 API 라우트는 backend/app/api/ 에서 관리

## 개발 프로세스
- CRITICAL: 새 기능 구현 시 반드시 테스트를 먼저 작성하고, 테스트가 통과하는 구현을 작성할 것 (TDD)
- 커밋 메시지는 conventional commits 형식을 따를 것 (feat:, fix:, docs:, refactor:)

## 변경 이력 관리
- CRITICAL: 코드 수정 작업 완료 시 반드시 CHANGELOG.md의 [Unreleased] 섹션에 conventional commits 형식으로 1줄 기록할 것
- CRITICAL: [Unreleased]에 10건 이상 쌓이면, 사용자에게 "docs 동기화가 필요합니다" 안내할 것
- docs 동기화 시: ARCHITECTURE.md + ADR.md + PRD.md를 현재 코드베이스 기준으로 업데이트하고, [Unreleased] 항목을 새 버전 태그로 정리할 것

## 명령어

### Frontend
```bash
cd frontend && npm run dev      # 개발 서버 (port 5173)
cd frontend && npm run build    # 프로덕션 빌드
cd frontend && npm run lint     # ESLint
```

### Backend
```bash
cd backend && uvicorn app.main:app --reload --port 8000   # 개발 서버
cd backend && pytest                                       # 테스트
```

### Harness
```bash
python3 scripts/execute.py <phase-dir>          # 순차 실행
python3 scripts/execute.py <phase-dir> --push   # 실행 후 push
```
