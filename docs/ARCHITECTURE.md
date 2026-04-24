# 아키텍처

## 디렉토리 구조
```
new-project/
├── frontend/               # React + TypeScript (Vite)
│   ├── src/
│   │   ├── components/     # UI 컴포넌트
│   │   ├── types/          # TypeScript 타입 정의
│   │   ├── hooks/          # Custom hooks
│   │   ├── services/       # API 호출 래퍼 (백엔드만 호출)
│   │   ├── utils/          # 유틸리티 함수
│   │   ├── App.tsx         # 루트 컴포넌트
│   │   └── main.tsx        # 엔트리 포인트
│   └── public/             # 정적 파일
│
├── backend/                # FastAPI (Python)
│   ├── app/
│   │   ├── api/            # API 라우트 핸들러
│   │   ├── core/           # 설정, 보안, 미들웨어
│   │   ├── models/         # DB 모델 (SQLAlchemy 등)
│   │   ├── schemas/        # Pydantic 스키마
│   │   ├── services/       # 비즈니스 로직 + AI 서비스
│   │   └── main.py         # FastAPI 앱 인스턴스
│   └── tests/              # pytest 테스트
│
├── docs/                   # 프로젝트 문서
│   ├── ARCHITECTURE.md     # 이 파일
│   ├── PRD.md              # 기획 문서
│   ├── ADR.md              # 아키텍처 결정 기록
│   └── UI_GUIDE.md         # UI 디자인 가이드
│
├── scripts/                # 하네스 스크립트
│   ├── execute.py          # 하네스 실행기
│   └── test_execute.py     # 실행기 테스트
│
├── phases/                 # 하네스 phase 디렉토리
│   ├── index.json          # 전체 phase 현황
│   └── {task-name}/        # 각 task별 디렉토리
│
└── GEMINI.md               # 프로젝트 규칙 (AI 가이드)
```

## 패턴
- 프론트엔드: 컴포넌트 기반 아키텍처. 재사용 가능한 컴포넌트는 components/에 분리
- 백엔드: 레이어드 아키텍처 (API → Service → Model)
- AI 통합: 모든 Gemini API 호출은 backend/app/services/ 에서만 수행

## 데이터 흐름
```
사용자 입력 → React Component → API Service (fetch) → FastAPI Route → Service Layer → Gemini API → 응답 → React UI 업데이트
```

## 상태 관리
- 서버 상태: React hooks (useState, useEffect) + API 호출
- 클라이언트 상태: useState / useReducer
- 필요시 Context API 사용 (전역 상태 최소화)
