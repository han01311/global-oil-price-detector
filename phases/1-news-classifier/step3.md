# Step 3: 과거 뉴스-유가 매핑 데이터 적재

## 목표
GDELT 과거 데이터와 EIA 과거 유가를 매핑하여 ChromaDB에 초기 학습 데이터(seed data)를 적재한다. 이 데이터가 Market Memory의 기반이 된다.

## 작업

### 1. 시드 데이터 수집 스크립트
`backend/app/services/historical_loader.py`를 구현한다:

```python
class HistoricalLoader:
    """과거 뉴스-유가 매핑 데이터를 ChromaDB에 적재"""

    # 주요 유가 이벤트 시드 데이터 (수동 큐레이션)
    SEED_EVENTS = [
        {
            "date": "2020-03-09",
            "title": "Saudi-Russia Oil Price War Begins",
            "summary": "사우디-러시아 감산 협상 결렬, 사우디 대폭 증산 선언",
            "category": "supply",
            "impact_score": -5,
        },
        {
            "date": "2020-04-20",
            "title": "WTI Crude Turns Negative for First Time",
            "summary": "코로나 팬데믹으로 수요 폭락, WTI 사상 첫 마이너스 기록",
            "category": "demand",
            "impact_score": -5,
        },
        {
            "date": "2022-02-24",
            "title": "Russia Invades Ukraine",
            "summary": "러시아 우크라이나 침공, 에너지 공급 불안 급증",
            "category": "geopolitics",
            "impact_score": 5,
        },
        # ... 최소 30개 주요 이벤트
    ]

    async def load_seed_events(self):
        """시드 이벤트를 ChromaDB에 적재"""
        # 각 이벤트의 실제 유가 변동률을 EIA에서 조회
        # Market Memory에 저장
        ...

    async def backfill_from_gdelt(self, start_year: int, end_year: int):
        """GDELT에서 과거 에너지 이벤트를 대량 수집하여 적재"""
        # GDELT DOC API로 oil/crude/OPEC 키워드 검색
        # Gemini로 분류
        # EIA 유가와 매핑
        # ChromaDB에 적재
        ...
```

### 2. 시드 이벤트 목록 확충
최소 30개의 주요 유가 이벤트를 포함한다:
- 2014 유가 폭락 (셰일 혁명)
- 2016 OPEC 감산 합의
- 2018 이란 제재 복원
- 2019 사우디 아람코 드론 공격
- 2020 코로나 + 유가전쟁
- 2021 수에즈 운하 에버기븐호
- 2022 러시아-우크라이나 전쟁
- 2023 OPEC+ 자발적 감산
- 2024 중동 긴장 고조 (이란-이스라엘)

### 3. 적재 명령어
```bash
cd backend && python -m app.services.historical_loader
```
스크립트가 독립 실행 가능하도록 `if __name__ == "__main__"` 블록을 추가한다.

### 4. 테스트
`backend/tests/test_historical_loader.py`:
- 시드 이벤트 적재 성공 검증
- 유가 변동률 매핑 정확도 검증
- ChromaDB에 적재된 건수 확인

## AC (Acceptance Criteria)
1. 최소 30개 시드 이벤트가 ChromaDB에 적재된다
2. 각 이벤트에 실제 유가 변동률(1d/7d/30d)이 매핑되어 있다
3. `market_memory.search_similar("OPEC production cut")` 시 관련 사례가 반환된다
4. 카테고리별 이벤트 분포가 확인된다
5. `pytest backend/tests/test_historical_loader.py` 가 통과한다
