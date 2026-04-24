# Architecture Decision Records

## 철학
{프로젝트의 핵심 가치관 (예: MVP 속도 최우선. 외부 의존성 최소화. 작동하는 최소 구현을 선택.)}

---

### ADR-001: React + Vite 선택
**결정**: 프론트엔드 프레임워크로 React + Vite + TypeScript를 선택
**이유**: 빠른 HMR, 간결한 설정, TypeScript 네이티브 지원
**트레이드오프**: SSR이 필요하면 Next.js로 마이그레이션 필요

### ADR-002: FastAPI 선택
**결정**: 백엔드 프레임워크로 FastAPI를 선택
**이유**: Python 생태계 (AI/ML 라이브러리), 자동 API 문서, async 지원, 타입 힌트 기반 검증
**트레이드오프**: Node.js 대비 프론트엔드와 언어 통일 불가

### ADR-003: Google AI Studio (Gemini API)
**결정**: AI 서비스로 Google AI Studio (Gemini API)를 선택
**이유**: 최신 멀티모달 모델, 한국어 성능, 비용 효율
**트레이드오프**: OpenAI/Anthropic 대비 커뮤니티 리소스가 상대적으로 적음
