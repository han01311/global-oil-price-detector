# 프로젝트: {프로젝트명}

## 기술 스택
- Frontend: React + TypeScript (Vite)
- Backend: FastAPI (Python)
- AI: Google AI Studio (Gemini API)
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
