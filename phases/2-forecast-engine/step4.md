# Step 4: AI 유가 브리핑 자동 생성기 구현

## 목표
추정 엔진이 산출한 예상 유가와 유사 과거 사례를 종합하여 "왜 이런 가격을 추정했는지" 설명하는 일일 전망 리포트를 Gemini로 자동 생성한다.

## 작업

### 1. 브리핑 생성기 서비스
`backend/app/services/briefing_generator.py`를 구현한다:

```python
class BriefingGenerator:
    """AI 유가 브리핑 자동 생성기"""

    async def generate_briefing(self, forecast: ForecastResult,
                                 classified_articles: list[dict],
                                 similar_events: list[dict]) -> Briefing:
        """일일 유가 브리핑 생성"""

        prompt = self._build_briefing_prompt(
            forecast=forecast,
            articles=classified_articles,
            similar_events=similar_events,
        )

        # Gemini로 브리핑 생성
        response = await self._call_gemini(prompt)

        return Briefing(
            date=datetime.now().strftime("%Y-%m-%d"),
            summary=response["summary"],           # 3줄 핵심 요약
            key_factors=response["key_factors"],    # 주요 영향 요인 분석
            risk_scenarios=response["risk_scenarios"],  # 리스크 시나리오
            similar_cases=response["similar_cases"],    # 과거 유사 사례 비교
            price_outlook=response["price_outlook"],    # 가격 전망
            confidence_note=response["confidence_note"],# 신뢰도 코멘트
        )

    def _build_briefing_prompt(self, ...) -> str:
        """브리핑용 프롬프트 구성"""
        # 포함 내용:
        # 1. 현재 유가 및 추정 결과 (밴드)
        # 2. 오늘 주요 뉴스 (분류 결과 포함)
        # 3. 유사 과거 사례 (당시 유가 변동 포함)
        # 4. 출력 형식 강제 (JSON)
        ...
```

### 2. 브리핑 스키마
`backend/app/schemas/forecast.py`에 추가:

```python
class BriefingKeyFactor(BaseModel):
    category: str           # 6대 카테고리
    description: str        # 요인 설명
    impact: str             # "bullish" | "bearish" | "neutral"
    score: int              # -5 ~ +5

class RiskScenario(BaseModel):
    scenario: str           # 시나리오 설명
    probability: str        # "high" | "medium" | "low"
    price_impact: str       # 예: "+$3~5"

class SimilarCase(BaseModel):
    event: str              # 과거 이벤트명
    date: str
    similarity: float
    actual_impact: str      # 당시 실제 유가 변동

class Briefing(BaseModel):
    date: str
    summary: str                          # 3줄 핵심 요약
    key_factors: list[BriefingKeyFactor]   # 주요 요인 (최대 5개)
    risk_scenarios: list[RiskScenario]     # 리스크 시나리오 (최대 3개)
    similar_cases: list[SimilarCase]       # 과거 유사 사례 (최대 3개)
    price_outlook: str                     # 가격 방향성 전망
    confidence_note: str                   # 신뢰도/한계 코멘트
    generated_at: str
```

### 3. 브리핑 캐싱
- 하루 1회 생성, JSON으로 캐시
- 캐시 경로: `backend/data/processed/briefings/YYYY-MM-DD.json`

### 4. 테스트
`backend/tests/test_briefing_generator.py`:
- Gemini 응답 mocking
- 프롬프트에 필요한 컨텍스트가 포함되는지 확인
- 브리핑 스키마 검증
- 캐시 동작 확인

## AC (Acceptance Criteria)
1. Gemini가 구조화된 JSON 형식의 브리핑을 생성한다
2. 브리핑에 핵심 요약, 주요 요인, 리스크 시나리오, 과거 사례가 포함된다
3. 추정 유가 수치와 뉴스 분석이 브리핑에 반영된다
4. 하루 1회 캐싱이 동작한다
5. `pytest backend/tests/test_briefing_generator.py` 가 통과한다
