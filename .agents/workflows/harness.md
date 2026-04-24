---
description: 하네스(Harness) 실행 — phase별 step을 Gemini로 자동 실행
---

# Harness 실행 워크플로우

하네스는 `phases/` 디렉토리에 정의된 step들을 Gemini API를 통해 순차 실행하는 자동화 프레임워크입니다.

## 사전 조건

1. `GEMINI_API_KEY`가 설정되어 있어야 합니다:
   ```bash
   export GEMINI_API_KEY=your-key
   ```
   또는 `backend/.env` 파일에 `GEMINI_API_KEY=your-key`를 추가합니다.

2. `google-generativeai` 패키지가 설치되어 있어야 합니다:
   ```bash
   pip install google-generativeai
   ```

## Phase 목록 확인

현재 프로젝트의 phase 구조를 확인합니다:

// turbo
1. `cat phases/index.json | python3 -m json.tool`

## Phase 실행

특정 phase를 실행합니다. `<phase-dir>`을 실행할 phase 디렉토리명으로 교체하세요.

2. `python3 scripts/execute.py <phase-dir>`

실행 후 자동으로 git push까지 하려면:

3. `python3 scripts/execute.py <phase-dir> --push`

## Phase 디렉토리 구조

각 phase는 아래 구조를 따릅니다:

```
phases/<phase-dir>/
├── index.json      # step 목록 및 상태 관리
├── step1.md        # step 1 작업 지시서
├── step2.md        # step 2 작업 지시서
├── ...
├── step1-output.json  # (실행 후 생성) step 1 결과
└── step2-output.json  # (실행 후 생성) step 2 결과
```

## 현재 Phase 목록

| Phase | 디렉토리명 | 설명 | Steps |
|-------|-----------|------|-------|
| 0 | `0-data-foundation` | 데이터 수집 & 파이프라인 구축 | 6 |
| 1 | `1-news-classifier` | AI 뉴스 요인 분류기 & Market Memory | 5 |
| 2 | `2-forecast-engine` | 하이브리드 유가 추정 엔진 | 6 |
| 3 | `3-dashboard-ui` | 대시보드 UI 구축 | 7 |

## 실행 예시

```bash
# Phase 0 실행 (데이터 파이프라인)
python3 scripts/execute.py 0-data-foundation

# Phase 0 실행 후 자동 push
python3 scripts/execute.py 0-data-foundation --push

# Phase 1 실행 (뉴스 분류기)
python3 scripts/execute.py 1-news-classifier
```

## 트러블슈팅

- **step이 error 상태**: `phases/<dir>/index.json`에서 해당 step의 `status`를 `"pending"`으로 변경 후 재실행
- **step이 blocked 상태**: `blocked_reason`을 확인하고 필요한 조치 (API 키 등) 후 `status`를 `"pending"`으로 변경
- **API 키 없음**: `backend/.env`에 필요한 API 키를 설정
