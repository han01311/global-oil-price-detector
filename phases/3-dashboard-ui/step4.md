# Step 4: 뉴스 익스플로러 & 요인 필터 구현

## 목표
분류된 뉴스 기사를 카테고리별로 필터링하고 탐색할 수 있는 뉴스 익스플로러 컴포넌트를 구현한다.

## 작업

### 1. NewsExplorer 컴포넌트
`frontend/src/components/NewsExplorer/NewsExplorer.tsx`:

- **카테고리 필터 탭**: 6대 카테고리 + 전체(All) 탭
  - 각 탭에 카테고리 색상 뱃지와 기사 수 표시
- **기사 목록**: 카드형 기사 목록
  - 제목, 출처, 시간, 카테고리 뱃지, Impact Score
  - Impact Score는 색상으로 표현 (+ = 오렌지, - = 블루, 크기로 강도)
- **정렬**: 시간순 / Impact Score순 토글
- **기사 클릭**: 원문 URL 새 탭으로 열기

### 2. NewsCard 컴포넌트
`frontend/src/components/NewsExplorer/NewsCard.tsx`:

```
┌──────────────────────────────────────┐
│ [GEOPOLITICS] [+4]                   │
│ Iran sanctions tighten as...         │
│ Reuters · 2시간 전                    │
│ "이란 제재 강화로 공급 축소 우려..."     │
└──────────────────────────────────────┘
```

- 카테고리 뱃지 (Badge 컴포넌트 활용)
- Impact Score 표시 (크기 + 색상)
- 출처 + 시간
- 영향 요약 (impact_summary)

### 3. 유사 사례 팝업
기사 카드에 "유사 사례" 버튼:
- 클릭 시 해당 기사와 유사한 과거 사례를 ChromaDB에서 검색
- 팝오버에 과거 유사 이벤트 목록 표시 (날짜, 당시 유가 변동률)

### 4. 데이터 훅
`frontend/src/hooks/useNewsData.ts`:
```typescript
export function useClassifiedNews(category?: string) {
  ...
}
```

## AC (Acceptance Criteria)
1. 분류된 뉴스 기사가 카드형으로 렌더링된다
2. 카테고리 필터 탭이 동작한다
3. 각 기사에 카테고리 뱃지와 Impact Score가 표시된다
4. "유사 사례" 버튼 클릭 시 과거 사례가 표시된다
5. 기사 클릭 시 원문 URL로 이동한다
