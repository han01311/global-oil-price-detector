import asyncio
import logging
import pandas as pd
from datetime import datetime, timedelta, timezone
import hashlib

# Adjust imports for standalone script execution
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.data_collector import DataCollector
from app.services.market_memory import MarketMemory
from app.utils.price_utils import calculate_price_changes

logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

class HistoricalLoader:
    """Loads historical news-price mapping data into ChromaDB."""

    SEED_EVENTS = [
        # 2014-2015 Oil Glut
        {"date": "2014-11-27", "title": "OPEC Decides Against Production Cut, Fueling Price Collapse", "summary": "OPEC의 감산 합의 실패로 유가가 급락하며 2010년대 중반 유가 하락세를 가속화시켰습니다.", "category": "supply", "impact_score": -5},
        {"date": "2015-08-24", "title": "Black Monday in China Sparks Global Selloff, Oil Plummets", "summary": "중국 증시 폭락이 글로벌 경기 둔화 우려를 키우며 유가 수요 전망을 어둡게 했습니다.", "category": "demand", "impact_score": -4},

        # 2016-2018 Recovery and Volatility
        {"date": "2016-11-30", "title": "OPEC Agrees to First Production Cut in 8 Years", "summary": "OPEC이 8년 만에 감산에 합의하면서 장기 저유가 국면을 마감하는 신호탄이 되었습니다.", "category": "supply", "impact_score": 4},
        {"date": "2018-05-08", "title": "US Withdraws from Iran Nuclear Deal, Reimposes Sanctions", "summary": "미국의 이란 핵협정 탈퇴 및 제재 복원으로 이란산 원유 공급 차질 우려가 커졌습니다.", "category": "geopolitics", "impact_score": 3},
        {"date": "2018-10-03", "title": "Crude Oil Hits Four-Year High Amid Iran Sanctions and Supply Fears", "summary": "이란 제재와 베네수엘라 생산 차질 등 공급 불안이 겹치며 유가가 4년 만에 최고치를 기록했습니다.", "category": "supply", "impact_score": 3},

        # 2019 Events
        {"date": "2019-09-14", "title": "Drone Attack on Saudi Aramco Facilities Halts 5% of Global Supply", "summary": "사우디 아람코 석유 시설 피격으로 전 세계 공급량의 5%가 일시 중단되며 유가가 급등했습니다.", "category": "geopolitics", "impact_score": 5},

        # 2020 COVID-19 and Price War
        {"date": "2020-03-09", "title": "Saudi-Russia Oil Price War Begins After OPEC+ Deal Collapses", "summary": "OPEC+ 감산 협상 결렬 후 사우디가 증산을 선언하며 유가 전쟁이 시작되었습니다.", "category": "supply", "impact_score": -5},
        {"date": "2020-04-20", "title": "WTI Crude Price Turns Negative for the First Time in History", "summary": "코로나19 팬데믹으로 인한 수요 증발과 저장 공간 부족으로 WTI 유가가 사상 처음 마이너스를 기록했습니다.", "category": "demand", "impact_score": -5},

        # 2021 Recovery and Supply Chain Issues
        {"date": "2021-03-23", "title": "Ever Given Ship Blocks Suez Canal, Disrupting Global Trade and Oil Shipments", "summary": "수에즈 운하가 에버기븐호로 막히면서 원유 수송에 차질이 발생했습니다.", "category": "supply", "impact_score": 2},
        {"date": "2021-11-26", "title": "New COVID-19 Variant 'Omicron' Sparks Fears of Renewed Lockdowns and Hits Oil Prices", "summary": "오미크론 변이 바이러스 출현으로 봉쇄 조치 및 항공유 수요 감소 우려가 커졌습니다.", "category": "demand", "impact_score": -3},

        # 2022 Russia-Ukraine War
        {"date": "2022-02-24", "title": "Russia Invades Ukraine, Sparking Global Energy Crisis", "summary": "러시아의 우크라이나 침공으로 러시아산 에너지 공급에 대한 제재 우려가 커지며 유가가 급등했습니다.", "category": "geopolitics", "impact_score": 5},
        {"date": "2022-03-08", "title": "US and UK Announce Ban on Russian Oil Imports", "summary": "미국과 영국의 러시아산 원유 수입 금지 조치로 공급 불안이 더욱 심화되었습니다.", "category": "geopolitics", "impact_score": 4},
        {"date": "2022-06-14", "title": "Oil Prices Surge as IEA Warns of Worsening Supply Deficit", "summary": "국제에너지기구(IEA)가 공급 부족 심화를 경고하며 유가 상승세가 이어졌습니다.", "category": "supply", "impact_score": 3},
        {"date": "2022-12-05", "title": "G7 Implements Price Cap on Russian Seaborne Oil", "summary": "G7 국가들이 러시아산 원유에 대한 가격 상한제를 도입하여 시장에 불확실성을 더했습니다.", "category": "geopolitics", "impact_score": -2},

        # 2023 OPEC+ Cuts and Geopolitics
        {"date": "2023-04-02", "title": "OPEC+ Announces Surprise Production Cut of Over 1 Million BPD", "summary": "OPEC+가 시장의 예상을 깨고 100만 배럴 이상의 자발적 추가 감산을 발표했습니다.", "category": "supply", "impact_score": 4},
        {"date": "2023-06-04", "title": "Saudi Arabia Pledges Deeper Voluntary Oil Output Cut", "summary": "사우디아라비아가 단독으로 추가 감산을 약속하며 유가 부양 의지를 보였습니다.", "category": "supply", "impact_score": 3},
        {"date": "2023-10-07", "title": "Hamas Attacks Israel, Igniting Fears of Wider Middle East Conflict", "summary": "하마스의 이스라엘 공격으로 중동 지역의 지정학적 리스크가 고조되었습니다.", "category": "geopolitics", "impact_score": 3},

        # 2024 Middle East Tensions
        {"date": "2024-01-12", "title": "US and UK Launch Airstrikes Against Houthi Targets in Yemen", "summary": "홍해 선박 공격에 대응한 미국과 영국의 예멘 후티 반군 공습으로 중동 긴장이 격화되었습니다.", "category": "geopolitics", "impact_score": 3},
        {"date": "2024-04-13", "title": "Iran Launches Direct Drone and Missile Attack on Israel", "summary": "이란이 이스라엘 본토를 직접 공격하며 전면전 우려가 커졌으나, 확전되지 않으며 영향은 제한되었습니다.", "category": "geopolitics", "impact_score": 2},
        
        # Additional Macro/Demand Events
        {"date": "2015-12-16", "title": "US Federal Reserve Raises Interest Rates for First Time Since 2006", "summary": "미 연준이 금융위기 이후 첫 금리 인상을 단행하며 달러 강세와 원자재 가격 하락 압력을 가했습니다.", "category": "macro", "impact_score": -2},
        {"date": "2016-06-23", "title": "Brexit: UK Votes to Leave the European Union", "summary": "영국의 EU 탈퇴 결정으로 글로벌 경제 불확실성이 커지며 안전자산 선호 현상이 나타났습니다.", "category": "macro", "impact_score": -2},
        {"date": "2019-08-05", "title": "US-China Trade War Escalates with New Tariffs", "summary": "미중 무역전쟁 격화로 글로벌 교역 및 경제 성장 둔화 우려가 커져 원유 수요에 부담을 주었습니다.", "category": "demand", "impact_score": -3},
        {"date": "2022-07-13", "title": "US Inflation Hits 9.1%, a 40-Year High, Fueling Recession Fears", "summary": "미국의 높은 인플레이션이 공격적인 금리 인상을 유발하고 경기 침체 우려를 키웠습니다.", "category": "macro", "impact_score": -3},
        {"date": "2023-03-10", "title": "Silicon Valley Bank Collapses, Sparking Banking Sector Turmoil", "summary": "SVB 파산 사태로 금융 시스템 리스크가 부각되며 경기 침체 우려가 다시 커졌습니다.", "category": "macro", "impact_score": -3},

        # Climate/ESG
        {"date": "2015-12-12", "title": "Paris Agreement on Climate Change Adopted", "summary": "파리 기후 협약 채택으로 장기적인 화석 연료 수요 감소에 대한 전망이 제기되었습니다.", "category": "climate", "impact_score": -1},
        {"date": "2021-08-29", "title": "Hurricane Ida Hits Gulf of Mexico, Shutting Down 95% of Oil Production", "summary": "허리케인 아이다가 멕시코만 석유 생산 시설에 큰 피해를 입히며 단기 공급 차질을 빚었습니다.", "category": "climate", "impact_score": 3},

        # Speculation
        {"date": "2017-11-20", "title": "Hedge Funds Amass Record Bullish Bets on Crude Oil", "summary": "헤지펀드들이 유가 상승에 대한 기록적인 순매수 포지션을 구축하며 시장 심리를 자극했습니다.", "category": "speculation", "impact_score": 2},
        {"date": "2020-03-30", "title": "Massive Contango in Oil Futures Market Signals Severe Glut", "summary": "원유 선물 시장에서 콘탱고가 심화되며 단기 공급 과잉과 저장 공간 부족 문제를 드러냈습니다.", "category": "speculation", "impact_score": -3},
        
        # More Geopolitics
        {"date": "2019-06-20", "title": "Iran Shoots Down US Drone, Tensions Escalate in Strait of Hormuz", "summary": "이란의 미군 드론 격추 사건으로 호르무즈 해협의 군사적 긴장이 최고조에 달했습니다.", "category": "geopolitics", "impact_score": 3},
        {"date": "2022-09-21", "title": "Putin Announces Partial Mobilization for Ukraine War", "summary": "푸틴 대통령의 부분 동원령 선포로 우크라이나 전쟁이 장기화될 것이라는 우려가 커졌습니다.", "category": "geopolitics", "impact_score": 2},
        {"date": "2024-02-16", "title": "Death of Alexei Navalny in Russian Prison Increases Political Tensions", "summary": "러시아 야권 지도자 나발니의 사망으로 서방과 러시아 간의 정치적 갈등이 심화되었습니다.", "category": "geopolitics", "impact_score": 1},
    ]

    def __init__(self):
        self.data_collector = DataCollector()
        self.market_memory = MarketMemory()

    async def load_seed_events(self):
        """Loads seed events into ChromaDB."""
        if not self.market_memory.is_available():
            logger.error("MarketMemory is not available. Aborting seed loading.")
            return

        logger.info(f"Found {len(self.SEED_EVENTS)} seed events to process.")

        # 1. Fetch all required price data in one go
        dates = [datetime.strptime(event["date"], "%Y-%m-%d") for event in self.SEED_EVENTS]
        min_date = min(dates) - timedelta(days=40) # Need 30 days prior for calculation
        max_date = max(dates) + timedelta(days=5)  # A small buffer
        
        logger.info(f"Fetching price history from {min_date.date()} to {max_date.date()}")
        price_history = await self.data_collector.collect_prices(min_date.strftime("%Y-%m-%d"), max_date.strftime("%Y-%m-%d"))
        if not price_history.prices:
            logger.error("Failed to fetch price history. Aborting.")
            return
        
        price_data = [p.model_dump() for p in price_history.prices]
        prices_df = pd.DataFrame(price_data)
        logger.info(f"Successfully fetched {len(prices_df)} price records.")

        # 2. Process and store each event
        loaded_count = 0
        for event in self.SEED_EVENTS:
            try:
                price_changes = calculate_price_changes(prices_df, event["date"])

                # Create a unique, deterministic ID
                event_str = f"{event['date']}-{event['title']}"
                event_id = hashlib.sha256(event_str.encode()).hexdigest()

                classified_article = {
                    "article": {
                        "id": event_id,
                        "title": event["title"],
                        "description": event["summary"],
                        "source": "Curated",
                        "url": f"http://petro-ax.com/seed/{event['date']}",
                        "published_at": f"{event['date']}T12:00:00Z",
                        "content_snippet": event["summary"],
                        "data_source": "seed"
                    },
                    "is_relevant": True,
                    "category": event["category"],
                    "sub_categories": [],
                    "impact_score": event["impact_score"],
                    "impact_summary": event["summary"],
                    "confidence": 1.0, # Curated data has max confidence
                    "classified_at": datetime.now(timezone.utc).isoformat()
                }

                await self.market_memory.store_event(classified_article, price_changes)
                loaded_count += 1
            except Exception as e:
                logger.error(f"Failed to process event '{event['title']}': {e}")
        
        logger.info(f"Successfully loaded {loaded_count} out of {len(self.SEED_EVENTS)} seed events into Market Memory.")

    async def backfill_from_gdelt(self, start_year: int, end_year: int):
        """(Not Implemented) Fetches historical energy events from GDELT and loads them."""
        logger.warning("backfill_from_gdelt is not yet implemented.")
        # Future implementation:
        # 1. Loop through months/years in the date range.
        # 2. Use GDELT DOC API to search for keywords (oil, crude, OPEC, etc.).
        # 3. For each article, classify it using NewsClassifier.
        # 4. Map to EIA price data.
        # 5. Store in ChromaDB via MarketMemory.
        pass


if __name__ == "__main__":
    async def main():
        print("--- Starting Historical Data Loader ---")
        loader = HistoricalLoader()
        await loader.load_seed_events()
        print("--- Seed events loading process completed. ---")

    # This allows running the script from the `backend` directory with `python -m app.services.historical_loader`
    asyncio.run(main())
