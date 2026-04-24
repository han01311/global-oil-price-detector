# Step 6: 요인 게이지 & 대시보드 통합

## 목표
6대 요인별 현재 스코어를 시각적으로 표시하는 게이지 컴포넌트를 구현하고, 모든 컴포넌트를 대시보드에 통합한다.

## 작업

### 1. FactorGauge 컴포넌트
`frontend/src/components/FactorGauge/FactorGauge.tsx`:

```
┌─ FACTOR ANALYSIS ────────────────────┐
│                                      │
│ 지정학   ████████░░  +3.2  (5건)     │
│ 공급     ██████░░░░  +2.1  (3건)     │
│ 수요     ██░░░░░░░░  +0.8  (2건)     │
│ 거시경제 ░░░░██░░░░  -1.2  (4건)     │
│ 기후     ░░░░░░░░░░   0.0  (0건)     │
│ 투기     ░░░░░█░░░░  -0.5  (1건)     │
│                                      │
│ ─────────────────────────────────    │
│ 종합 센티먼트: +1.4 (약 상승)         │
│ 분석 기사: 15건 · 갱신: 12분 전      │
└──────────────────────────────────────┘
```

- 수평 바 차트: 각 카테고리별 평균 스코어를 -5~+5 범위로 표시
- 바 색상: 각 카테고리 고유 색상
- 양의 값은 오른쪽, 음의 값은 왼쪽
- 종합 센티먼트: 전체 평균 스코어 + 방향성 라벨

### 2. 대시보드 통합
모든 컴포넌트를 `Dashboard.tsx`에 배치:

```typescript
function Dashboard() {
  return (
    <div className="dashboard">
      <Header />
      <main className="dashboard-grid">
        <section className="chart-section">
          <PriceChart />
        </section>
        <aside className="sidebar">
          <FactorGauge />
          <BriefingViewer />
        </aside>
      </main>
      <section className="news-section">
        <NewsExplorer />
      </section>
    </div>
  );
}
```

### 3. 차트 ↔ 뉴스 인터랙션 연결
- 차트 핀포인트 클릭 → 뉴스 익스플로러가 해당 시점 기사로 필터
- 뉴스 카테고리 탭 클릭 → 차트에서 해당 카테고리 마커만 강조
- 상태 공유: Context API 또는 props drilling

### 4. 반응형 처리
- 1440px 이상: 2-column 그리드
- 1024px 이하: 1-column 스택
- 모바일: 섹션별 스크롤

## AC (Acceptance Criteria)
1. FactorGauge가 6대 요인 스코어를 바 차트로 표시한다
2. 모든 컴포넌트가 대시보드에 올바르게 배치된다
3. 차트 ↔ 뉴스 간 인터랙션이 동작한다
4. 반응형 레이아웃이 브레이크포인트에 따라 변한다
5. `cd frontend && npm run dev`로 전체 대시보드가 확인된다
