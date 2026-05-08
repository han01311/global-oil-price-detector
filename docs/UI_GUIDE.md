# UI 디자인 및 UX 가이드 — OilLens

## 디자인 원칙
1. **도구처럼 보여야 한다.** 마케팅 페이지가 아니라 매일 쓰는 금융 터미널. 정보 밀도 우선.
2. **데이터가 주인공이다.** 장식은 최소화하고, 숫자와 차트가 시선을 지배해야 한다.
3. **즉시 읽혀야 한다.** 상승=오렌지, 하락=블루. 색상만으로 상황을 파악할 수 있어야 한다.
4. **대기 시간을 숨겨라 (Perceived Performance).** 로딩 중에도 화면 골격을 유지하여 인지적 스트레스를 낮춘다.

## AI 슬롭 안티패턴 — 하지 마라
| 금지 사항 | 이유 |
|-----------|------|
| backdrop-filter: blur() | glass morphism은 AI 템플릿의 가장 흔한 징후 |
| gradient-text (배경 그라데이션 텍스트) | AI가 만든 SaaS 랜딩의 1번 특징 |
| "Powered by AI" 배지 | 기능이 아니라 장식. 사용자에게 가치 없음 |
| box-shadow 글로우 애니메이션 | 네온 글로우 = AI 슬롭 |
| 보라/인디고 브랜드 색상 | "AI = 보라색" 클리셰 |
| 모든 카드에 동일한 rounded-2xl | 균일한 둥근 모서리는 템플릿 느낌 |
| 배경 gradient orb (blur-3xl 원형) | 모든 AI 랜딩 페이지에 있는 장식 |
| 화면 전체를 덮는 Loading Overlay | 작업 흐름을 끊고 답답함을 유발함 |

## 색상
### 배경
| 용도 | 값 | 비고 |
|------|------|------|
| 페이지 | `#0a0a0a` | 완전 블랙에 가까운 다크 |
| 카드 | `#141414` | 미세하게 밝은 그레이 |
| 카드 호버 | `#1a1a1a` | 인터랙션 피드백 |
| 보더 | `#262626` | 카드/섹션 구분선 |
| 스켈레톤 기본 | `#262626` | 로딩 상태 차징 배경 |
| 스켈레톤 애니메이션 | `#333333` | Pulse 애니메이션 그라데이션 |

### 텍스트
| 용도 | 값 |
|------|------|
| 주 텍스트 (숫자, 제목) | `#ffffff` |
| 본문 | `#d4d4d4` |
| 보조 (라벨, 캡션) | `#a3a3a3` |
| 비활성/빈 상태 (Empty) | `#737373` |

### 시맨틱 / 데이터 색상 (접근성 최소 명도대비 유지)
| 용도 | 값 | 사용처 |
|------|------|--------|
| **상승 (Bull)** | `#FF6B35` | 유가 상승, 양의 변동률, 상승 요인 뱃지 |
| **하락 (Bear)** | `#00D4FF` | 유가 하락, 음의 변동률, 하락 요인 뱃지 |
| 중립 | `#525252` | 변동 없음, 비활성 상태 |
| 경고 | `#FBBF24` | 높은 불확실성, 주의 필요 |
| 에러 | `#EF4444` | 시스템 에러, 데이터 로딩 실패, 치명적 예외 상황 |

### 6대 요인 카테고리 색상
| 카테고리 | 색상 | 뱃지 텍스트 |
|----------|------|-------------|
| geopolitics | `#EF4444` | 지정학 |
| supply | `#F97316` | 공급 |
| demand | `#3B82F6` | 수요 |
| macro | `#8B5CF6` | 거시경제 |
| climate | `#10B981` | 기후/ESG |
| speculation | `#EC4899` | 투기/심리 |

---

## 🚀 UX 상세 가이드 (사용자 경험 및 피드백)

### 1. 로딩 및 지연 모드 (Skeleton & Progressive Loading)
- **무한 스피너(Loader) 금지**: 초기 데이터 패칭 시 가운데 둥근 스피너 대신 화면 레이아웃이 동일한 **Skeleton UI** 표출.
- **점진적 로딩**: 백엔드 통신과 Gemma 4 AI 분석이 각각 다른 속도로 끝날 수 있음. 차트가 먼저 로드되면 차트는 먼저 보여주고, AI 브리핑 창만 독립적으로 `Pulse` 애니메이션의 스켈레톤을 유지. (화면 깜빡임 방지)

### 2. 빈 상태 및 에러 화면 (Empty / Error States)
- **Empty State**: 수집된 뉴스가 아예 없을 때, 빈 테이블을 두지 말고 회색 계열의 아이콘(예: 빈 박스)과 텍스트("선택한 날짜에 등록된 중요 뉴스/이벤트가 없습니다") 제공.
- **부분 에러(Partial Error)**: 뉴스 모듈 장애 시 차트까지 멈춰선 안 됨. 장애 모듈만 "데이터를 불러올 수 없습니다" 안내 문구와 [재시도(Refresh)] Outline 버튼 표출.
- **비침입성 알림(Toast)**: 저장 성공, 백그라운드 캐시 갱신 등은 화면 우측 하단의 Toast 알림(3초 뒤 사라짐)으로 비침입적으로 전달.

### 3. 마이크로 인터랙션 (Micro-Interactions & Affordances)
- **호버 (Hover)**: 버튼, 뉴스 카드, 링크 등 클릭 가능한 요소에 마우스를 올릴 때 미세한 배경색 변화(`var(--color-card-hover)`)로 즉각적인 피드백 제공.
- **툴팁 (Tooltips)**: 전문 용어(예: "WTI", "FRED API", "CAMEO 이벤트") 옆에 정보 아이콘(Info icon)을 배치하고, 마우스 호버 시 간결한 설명을 띄워줌. 
- **트랜지션 (Transitions)**: 오버피팅 되거나 너무 많은 애니메이션 금지. 탭 이동 및 필터 변환 시에는 딱딱하지되 부드러운 전환(Opacity/Transform 0.2s 이내) 활용. Optimistic UI를 지향하여 '필터 클릭 시 로딩 없이 즉시 뷰 변경(캐시 활용)' 원칙.

---

## 컴포넌트 규격
### 카드
```css
border-radius: 4px;
background: var(--color-card);
border: 1px solid var(--color-border);
padding: 20px;
```

### 버튼
```css
/* Primary */
border-radius: 4px;
background: var(--color-bull);
color: #0a0a0a;
font-weight: 600;
padding: 8px 16px;

/* Ghost / Error Retry */
background: transparent;
border: 1px solid var(--color-border);
color: var(--color-text-secondary);
```

... 이하 기존 스타일링 규칙 준수 ...

## 레이아웃 및 반응형 규칙 (Responsive)
- **전체 너비**: `max-width: 1440px` (금융 대시보드는 정보를 넓게 표시)
- **정렬**: 좌측 정렬 기본. 중앙 정렬 금지.
- **그리드**: CSS Grid 2-column (차트 70% + 사이드패널 30%)
- **모바일/태블릿 UX (Media Query < 1024px)**: 
  - 좌우 2-column을 **상하 1-column Stack 방식**으로 변경. 데스크토에서 1열이던 차트가 다소 작아지며, 뉴스 익스플로러와 브리핑 뷰어가 차트의 하단(Below) 탭 혹은 스크롤 형태로 밀려나는 선형 배열 구조 채택. 
  - 버튼 패딩은 태블릿 터치를 고려해 최소 타겟 사이즈(44px) 유지.

## 타이포그래피 (접근성 고려)
| 용도 | 스타일 |
|------|--------|
| 유가 숫자 (히어로) | `32px, font-weight: 700, tabular-nums` |
| 페이지 제목 | `20px, font-weight: 600` |
| 카드 제목 | `13px, font-weight: 600, text-transform: uppercase, letter-spacing: 0.05em` |
| 본문 (가독성 최적화) | `14px, line-height: 1.5` |
| 캡션/라벨 | `12px, color: var(--color-text-muted)` |
| 숫자 (tabular) | `font-variant-numeric: tabular-nums` |

## 애니메이션
- `fade-in`: opacity 0→1, 0.3s ease-out (카드 로딩)
- `slide-up`: translateY(8px)→0, 0.3s ease-out (리스트 아이템)
- `pulse`: opacity 0.5→1.0 반복 (Skeleton UI)
- 숫자 변경: CSS transition 0.2s (유가 업데이트)
- **그 외 모든 장식적 애니메이션 금지**

## 아이콘
- SVG 인라인, strokeWidth: 1.5
- 크기: 16px (인라인), 20px (버튼 내)
- 아이콘 컨테이너(둥근 배경 박스)로 감싸지 않는다
