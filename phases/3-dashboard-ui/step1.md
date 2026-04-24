# Step 1: 프론트엔드 의존성 및 디자인 시스템 구축

## 목표
프론트엔드에 필요한 패키지를 설치하고, UI_GUIDE.md에 정의된 디자인 시스템을 CSS 변수와 공통 컴포넌트로 구현한다.

## 작업

### 1. 패키지 설치
```bash
cd frontend && npm install recharts lightweight-charts react-router-dom
```

### 2. CSS 디자인 시스템
`frontend/src/index.css`를 UI_GUIDE.md에 맞게 구현한다:

```css
:root {
  /* 배경 */
  --color-bg: #0a0a0a;
  --color-card: #141414;
  --color-card-hover: #1a1a1a;
  --color-border: #262626;

  /* 텍스트 */
  --color-text-primary: #ffffff;
  --color-text-body: #d4d4d4;
  --color-text-secondary: #a3a3a3;
  --color-text-muted: #737373;

  /* 시맨틱 */
  --color-bull: #FF6B35;
  --color-bear: #00D4FF;
  --color-neutral: #525252;
  --color-warning: #FBBF24;
  --color-error: #EF4444;

  /* 카테고리 */
  --color-cat-geopolitics: #EF4444;
  --color-cat-supply: #F97316;
  --color-cat-demand: #3B82F6;
  --color-cat-macro: #8B5CF6;
  --color-cat-climate: #10B981;
  --color-cat-speculation: #EC4899;

  /* 서체 */
  font-family: 'Inter', 'Pretendard', -apple-system, sans-serif;
}
```

### 3. 공통 컴포넌트
`frontend/src/components/common/` 하위에:

- `Card.tsx` — 기본 카드 컴포넌트
- `Badge.tsx` — 카테고리 뱃지 (6대 요인 색상)
- `PriceDisplay.tsx` — 유가 숫자 표시 (상승/하락 색상)
- `Skeleton.tsx` — 로딩 스켈레톤
- `ErrorBoundary.tsx` — 에러 바운더리

### 4. 타입 정의
`frontend/src/types/` 하위에:

- `price.ts` — OilPrice, PriceHistory, MacroIndicator 타입
- `news.ts` — NewsArticle, ClassifiedArticle, FactorSummary 타입
- `forecast.ts` — ForecastResult, Briefing 타입

### 5. API 서비스 업데이트
`frontend/src/services/api.ts`를 업데이트하여 백엔드 API를 호출하는 함수를 구현한다:
- `fetchPriceHistory(startDate, endDate)`
- `fetchLatestPrices()`
- `fetchClassifiedNews(category?, limit?)`
- `fetchForecastEstimate()`
- `fetchTodayBriefing()`
- `fetchSimilarEvents(query)`
- `fetchFactorSummary()`

### 6. 폰트 로딩
`frontend/index.html`에 Inter 폰트를 추가한다.

## AC (Acceptance Criteria)
1. CSS 변수가 UI_GUIDE.md와 일치한다
2. 공통 컴포넌트(Card, Badge, PriceDisplay)가 렌더링된다
3. 타입 정의가 백엔드 스키마와 일치한다
4. API 서비스 함수가 올바른 URL을 호출한다
5. `cd frontend && npm run build` 가 에러 없이 완료된다
