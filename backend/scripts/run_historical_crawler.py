import asyncio
import argparse
import logging
import json
import os
from pathlib import Path

from app.core.database import Database
from app.services.archive_crawler import HistoricalArchiveCrawler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).parent.parent / "data" / "crawler_state.json"

def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"last_page": 0}

def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

async def main():
    parser = argparse.ArgumentParser(description="Historical Archive Crawler")
    parser.add_argument("--limit-pages", type=int, default=10, help="Number of pages to crawl in this run")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between article fetches (seconds)")
    parser.add_argument("--start-page", type=int, default=None, help="Force start page (ignores state file)")
    args = parser.parse_args()

    db = Database()
    await db.connect()

    crawler = HistoricalArchiveCrawler(db)

    state = load_state()
    start_page = args.start_page if args.start_page is not None else state["last_page"] + 1

    logger.info(f"Starting Historical Crawler from page {start_page} with limit {args.limit_pages}")

    # Create a small loop to update state after each page
    import httpx
    async with httpx.AsyncClient(headers=crawler.headers, timeout=20.0) as client:
        for page in range(start_page, start_page + args.limit_pages):
            articles = await crawler.crawl_oilprice_page(client, page, delay=args.delay)
            if not articles:
                logger.info(f"No articles found on page {page}. Stopping.")
                break
            
            upsert_count = await db.upsert_news_articles(articles)
            logger.info(f"Page {page} completed. Upserted {upsert_count} articles.")
            
            # Update state
            state["last_page"] = page
            save_state(state)
            
            await asyncio.sleep(args.delay * 2)

    await db.close()
    logger.info("Crawling batch finished.")

if __name__ == "__main__":
    # Windows/macOS event loop compatibility if needed
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
