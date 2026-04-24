# Step 3: 유가 추정 차트 컴포넌트 구현

## 목표
WTI/Brent 유가 이력을 캔들스틱 또는 라인 차트로 표시하고, 추정 밴드(신뢰구간)와 뉴스 핀포인트 마커를 오버레이하는 인터랙티브 차트를 구현한다.

## 작업

### 1. PriceChart 컴포넌트
`frontend/src/components/PriceChart/PriceChart.tsx`:

- **라인 차트**: WTI/Brent 일별 가격 라인
- **추정 밴드**: 미래 7일/30일 구간에 신뢰구간(Area)을 표시
  - 상승 방향: `rgba(255, 107, 53, 0.08)` (오렌지)
  - 하락 방향: `rgba(0, 212, 255, 0.08)` (블루)
- **뉴스 핀포인트**: 주요 뉴스 이벤트 발생 시점에 마커 표시
  - 마커 색상: 해당 뉴스의 카테고리 색상
  - 호버 시 툴팁: 뉴스 제목 + Impact Score
- **기간 선택**: 1M / 3M / 6M / 1Y / ALL 토글

### 2. 차트 스타일
- 배경: transparent
- 그리드 라인: `#1a1a1a` dashed
- 축 라벨: `12px, #737373`
- 크로스헤어: 마우스 위치에 가격/날짜 표시

### 3. 핀포인트 클릭 인터랙션
- 차트 위 뉴스 마커 클릭 시
- 해당 시점의 분류된 기사 목록을 사이드패널 또는 팝오버로 표시
- 유사 과거 사례 검색 결과도 함께 표시

### 4. Recharts 또는 Lightweight Charts 사용
- Recharts: `ComposedChart` (Line + Area + ReferenceDot)
- Lightweight Charts: `createChart` + `LineSeries` + `AreaSeries`
- 둘 중 더 적합한 라이브러리를 선택

### 5. 데이터 훅
`frontend/src/hooks/usePriceData.ts`:
```typescript
export function usePriceData(period: string) {
  // 가격 이력 + 추정 결과를 함께 fetching
  // period에 따라 start_date 계산
  ...
}
```

## AC (Acceptance Criteria)
1. WTI/Brent 유가 라인 차트가 렌더링된다
2. 추정 밴드(신뢰구간)가 미래 구간에 표시된다
3. 뉴스 핀포인트 마커가 카테고리 색상으로 표시된다
4. 마커 호버 시 툴팁이 표시된다
5. 기간 선택(1M/3M/6M/1Y)이 동작한다
