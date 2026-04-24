# Step 1: Gemini 기반 뉴스 요인 분류기 구현

## 목표
Gemini API를 사용하여 유가 관련 뉴스 기사를 6대 카테고리로 분류하고, 영향도 스코어(Impact Score)를 산출하는 서비스를 구현한다.

## 배경
- 6대 카테고리: `geopolitics`, `supply`, `demand`, `macro`, `climate`, `speculation`
- Impact Score: -5(강한 하락 압력) ~ +5(강한 상승 압력)
- Gemini가 JSON 포맷으로 구조화된 분류 결과를 반환해야 한다

## 작업

### 1. 뉴스 분류기 서비스
`backend/app/services/news_classifier.py`를 구현한다:

```python
class NewsClassifier:
    """Gemini 기반 뉴스 요인 분류기"""

    CATEGORIES = ["geopolitics", "supply", "demand", "macro", "climate", "speculation"]

    async def classify_article(self, article: dict) -> dict:
        """단일 기사를 분류하고 영향도를 평가한다"""
        # Gemini에게 기사 제목+설명+내용을 전달
        # 구조화된 JSON 응답 요청:
        # {
        #   "is_relevant": true/false,     # 유가 영향 기사인지
        #   "category": "geopolitics",     # 주 카테고리
        #   "sub_categories": ["supply"],  # 부 카테고리 (선택)
        #   "impact_score": 3,             # -5 ~ +5
        #   "impact_summary": "사우디 감산 연장으로 공급 축소 예상",
        #   "confidence": 0.85             # 분류 신뢰도
        # }
        ...

    async def classify_batch(self, articles: list[dict]) -> list[dict]:
        """여러 기사를 배치로 분류 (rate limit 고려)"""
        # 동시 요청 제한 (예: 5개씩)
        ...

    def _build_classification_prompt(self, article: dict) -> str:
        """분류용 프롬프트 생성"""
        ...
```

### 2. 프롬프트 설계
분류 프롬프트에 포함할 내용:
- 6대 카테고리 각각의 정의와 예시
- Impact Score 기준 가이드 (예: +5는 이란 핵시설 폭격 수준, +1은 미미한 감산 언급)
- JSON 응답 포맷 강제 (Gemini response_mime_type 활용)
- 유가와 무관한 기사를 걸러내는 `is_relevant` 필드

### 3. 분류 결과 스키마
`backend/app/schemas/news.py`에 추가:

```python
class ClassifiedArticle(BaseModel):
    article: NewsArticle
    is_relevant: bool
    category: str                    # 주 카테고리
    sub_categories: list[str] = []   # 부 카테고리
    impact_score: int                # -5 ~ +5
    impact_summary: str              # 영향 요약 (한 줄)
    confidence: float                # 0.0 ~ 1.0
    classified_at: str               # ISO 8601
```

### 4. 테스트
`backend/tests/test_news_classifier.py`:
- Gemini API 응답 mocking
- 프롬프트에 올바른 기사 내용이 포함되는지 검증
- JSON 파싱 실패 시 fallback 처리 테스트
- Impact Score 범위 검증(-5~+5)

## AC (Acceptance Criteria)
1. 기사를 입력하면 6대 카테고리 중 하나로 분류된다
2. Impact Score가 -5~+5 범위로 산출된다
3. 유가와 무관한 기사는 `is_relevant=false`로 필터링된다
4. 배치 처리 시 rate limit을 준수한다
5. `pytest backend/tests/test_news_classifier.py` 가 통과한다
