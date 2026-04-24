# Step 2: 대시보드 레이아웃 & 헤더 구현

## 목표
Petro-AX 대시보드의 전체 레이아웃과 헤더 컴포넌트를 구현한다. 금융 터미널 스타일의 프로페셔널한 레이아웃.

## 작업

### 1. 레이아웃 구조
```
┌──────────────────────────────────────────────┐
│ Header (로고, 현재 유가, 마지막 업데이트 시간)    │
├───────────────────────────┬──────────────────┤
│                           │  Factor Gauge    │
│  Price Chart (70%)        │  (6대 요인 스코어) │
│  (캔들스틱 + 밴드)         │                  │
│                           │  AI Briefing     │
│                           │  (요약 뷰어)      │
├───────────────────────────┴──────────────────┤
│  News Explorer (뉴스 목록 + 카테고리 필터)       │
└──────────────────────────────────────────────┘
```

### 2. Dashboard 컴포넌트
`frontend/src/components/Dashboard/Dashboard.tsx`:
- CSS Grid 2-column 레이아웃 (70% + 30%)
- 하단 뉴스 섹션은 full-width

### 3. Header 컴포넌트
`frontend/src/components/Dashboard/Header.tsx`:
- 왼쪽: Petro-AX 로고 (텍스트)
- 중앙: 현재 WTI / Brent 가격 (PriceDisplay 활용)
- 오른쪽: 마지막 데이터 업데이트 시간, 설정 아이콘

### 4. App.tsx 업데이트
- Dashboard를 기본 화면으로 렌더링
- 데이터 로딩 상태(Skeleton) 처리

### 5. 스타일링
- 각 컴포넌트별 CSS 파일 (`.module.css` 또는 일반 CSS 파일)
- UI_GUIDE.md의 간격, 색상 규칙 준수

## AC (Acceptance Criteria)
1. 대시보드가 다크 배경(`#0a0a0a`)에 렌더링된다
2. 헤더에 현재 유가가 상승/하락 색상으로 표시된다
3. 2-column 그리드 레이아웃이 반영된다
4. 로딩 중 Skeleton이 표시된다
5. `cd frontend && npm run dev`로 확인 가능하다
