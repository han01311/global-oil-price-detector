# UI 디자인 가이드 — Petro-AX

## 디자인 원칙
1. **도구처럼 보여야 한다.** 마케팅 페이지가 아니라 매일 쓰는 금융 터미널. 정보 밀도 우선.
2. **데이터가 주인공이다.** 장식은 최소화하고, 숫자와 차트가 시선을 지배해야 한다.
3. **즉시 읽혀야 한다.** 상승=오렌지, 하락=블루. 색상만으로 상황을 파악할 수 있어야 한다.

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

## 색상
### 배경
| 용도 | 값 | 비고 |
|------|------|------|
| 페이지 | `#0a0a0a` | 완전 블랙에 가까운 다크 |
| 카드 | `#141414` | 미세하게 밝은 그레이 |
| 카드 호버 | `#1a1a1a` | 인터랙션 피드백 |
| 보더 | `#262626` | 카드/섹션 구분선 |

### 텍스트
| 용도 | 값 |
|------|------|
| 주 텍스트 (숫자, 제목) | `#ffffff` |
| 본문 | `#d4d4d4` |
| 보조 (라벨, 캡션) | `#a3a3a3` |
| 비활성 | `#737373` |

### 시맨틱 / 데이터 색상
| 용도 | 값 | 사용처 |
|------|------|--------|
| **상승 (Bull)** | `#FF6B35` | 유가 상승, 양의 변동률, 상승 요인 뱃지 |
| **하락 (Bear)** | `#00D4FF` | 유가 하락, 음의 변동률, 하락 요인 뱃지 |
| 중립 | `#525252` | 변동 없음, 비활성 상태 |
| 경고 | `#FBBF24` | 높은 불확실성, 주의 필요 |
| 에러 | `#EF4444` | 시스템 에러, 데이터 로딩 실패 |

### 6대 요인 카테고리 색상
| 카테고리 | 색상 | 뱃지 텍스트 |
|----------|------|-------------|
| geopolitics | `#EF4444` | 지정학 |
| supply | `#F97316` | 공급 |
| demand | `#3B82F6` | 수요 |
| macro | `#8B5CF6` | 거시경제 |
| climate | `#10B981` | 기후/ESG |
| speculation | `#EC4899` | 투기/심리 |

## 컴포넌트
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

/* Ghost */
background: transparent;
border: 1px solid var(--color-border);
color: var(--color-text-secondary);
```

### 뱃지 (카테고리)
```css
border-radius: 2px;
padding: 2px 8px;
font-size: 11px;
font-weight: 600;
text-transform: uppercase;
letter-spacing: 0.05em;
/* 배경: 카테고리 색상 15% 투명도 */
/* 텍스트: 카테고리 색상 100% */
```

### 입력 필드
```css
border-radius: 4px;
background: #0a0a0a;
border: 1px solid var(--color-border);
padding: 10px 14px;
color: var(--color-text-primary);
```

## 레이아웃
- 전체 너비: `max-width: 1440px` (금융 대시보드는 넓게)
- 정렬: 좌측 정렬 기본. 중앙 정렬 금지.
- 간격: `gap: 12px` (카드 간), 섹션 간 `margin: 24px`
- 그리드: CSS Grid 2-column (차트 70% + 사이드패널 30%)

## 타이포그래피
| 용도 | 스타일 |
|------|--------|
| 유가 숫자 (히어로) | `32px, font-weight: 700, tabular-nums` |
| 페이지 제목 | `20px, font-weight: 600` |
| 카드 제목 | `13px, font-weight: 600, text-transform: uppercase, letter-spacing: 0.05em` |
| 본문 | `14px, line-height: 1.5` |
| 캡션/라벨 | `12px, color: var(--color-text-muted)` |
| 숫자 (tabular) | `font-variant-numeric: tabular-nums` |

## 애니메이션
- `fade-in`: opacity 0→1, 0.3s ease-out (카드 로딩)
- `slide-up`: translateY(8px)→0, 0.3s ease-out (리스트 아이템)
- 숫자 변경: CSS transition 0.2s (유가 업데이트)
- **그 외 모든 장식적 애니메이션 금지**

## 아이콘
- SVG 인라인, strokeWidth: 1.5
- 크기: 16px (인라인), 20px (버튼 내)
- 아이콘 컨테이너(둥근 배경 박스)로 감싸지 않는다

## 차트 스타일
- 배경: transparent (카드 배경과 동일)
- 그리드 라인: `#1a1a1a` dashed
- 축 라벨: `12px, #737373`
- 상승 캔들: `#FF6B35` (fill + stroke)
- 하락 캔들: `#00D4FF` (fill + stroke)
- 신뢰구간 밴드: `rgba(255, 107, 53, 0.08)` (상승 방향) / `rgba(0, 212, 255, 0.08)` (하락 방향)
- 뉴스 핀포인트: 카테고리 색상 원형 마커, hover 시 툴팁
