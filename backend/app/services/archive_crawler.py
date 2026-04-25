import asyncio
import httpx
import logging
import re
from datetime import datetime
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from hashlib import sha256

from app.core.database import Database

logger = logging.getLogger(__name__)

class HistoricalArchiveCrawler:
    """
    과거 뉴스 데이터(20년치 이상)를 크롤링하여 데이터베이스에 저장하는 클래스.
    IP 차단을 막기 위해 페이지 요청 간 딜레이를 적용합니다.
    """
    
    def __init__(self, db: Database):
        self.db = db
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.base_url = "https://oilprice.com"

    def _parse_oilprice_date(self, date_text: str) -> Optional[str]:
        """
        'By Author - Apr 24, 2026, 12:11 PM CDT' 형식의 문자열에서
        'Apr 24, 2026' 부분을 추출하여 ISO 8601 형식으로 변환합니다.
        """
        if not date_text:
            return None
        
        # ' - ' 뒤의 텍스트 파싱
        parts = date_text.split(" - ")
        if len(parts) > 1:
            date_str_with_time = parts[1].strip()
            # 'Apr 24, 2026, 12:11 PM CDT'에서 'Apr 24, 2026' 부분 추출 시도
            match = re.search(r'([A-Za-z]{3}\s+\d{1,2},\s+\d{4})', date_str_with_time)
            if match:
                try:
                    dt = datetime.strptime(match.group(1), "%b %d, %Y")
                    return dt.strftime("%Y-%m-%dT00:00:00Z")
                except ValueError:
                    pass
        return None

    async def crawl_oilprice_page(self, client: httpx.AsyncClient, page_num: int, delay: float = 2.0) -> List[Dict[str, Any]]:
        """
        OilPrice.com의 특정 페이지 번호에서 기사 목록과 상세 내용을 스크래핑합니다.
        """
        url = f"{self.base_url}/Energy/Crude-Oil/Page-{page_num}.html"
        logger.info(f"[ArchiveCrawler] Fetching OilPrice page {page_num}...")
        
        try:
            resp = await client.get(url, timeout=15.0)
            if resp.status_code == 404:
                logger.info(f"Page {page_num} not found. End of archive reached.")
                return []
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch page {page_num}: {e}")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        articles = soup.find_all('div', class_='categoryArticle')
        
        if not articles:
            logger.info(f"No articles found on page {page_num}.")
            return []

        crawled_data = []
        for article_div in articles:
            a_tag = article_div.find('a')
            if not a_tag or not a_tag.get('href'):
                continue
                
            link = a_tag['href']
            # 상대 경로인 경우 절대 경로로 변환
            if not link.startswith("http"):
                link = self.base_url + link
            
            # 본문 추출을 위해 상세 페이지 접근
            logger.debug(f"[ArchiveCrawler] Fetching article: {link}")
            try:
                # 딜레이 적용
                await asyncio.sleep(delay)
                a_resp = await client.get(link, timeout=15.0)
                a_resp.raise_for_status()
                
                a_soup = BeautifulSoup(a_resp.text, 'html.parser')
                title_tag = a_soup.find('h1')
                title = title_tag.text.strip() if title_tag else "No title"
                
                date_span = a_soup.find('span', class_='article_byline')
                date_text = date_span.text if date_span else ""
                published_at = self._parse_oilprice_date(date_text)
                
                # 본문 스니펫 추출 (첫 번째 p 태그나 특정 컨테이너 사용)
                content_div = a_soup.find('div', id='news-content') or a_soup.find('div', class_='singleArticle__content')
                content_snippet = ""
                if content_div:
                    paragraphs = content_div.find_all('p')
                    text_parts = [p.text.strip() for p in paragraphs if p.text.strip()]
                    content_snippet = " ".join(text_parts)[:500]  # 최대 500자
                
                article_info = {
                    "id": sha256(link.encode()).hexdigest(),
                    "title": title,
                    "description": None,
                    "source_name": "OilPrice.com",
                    "url": link,
                    "published_at": published_at,
                    "content_snippet": content_snippet,
                    "data_source": "historical_crawler"
                }
                crawled_data.append(article_info)
                
            except Exception as e:
                logger.error(f"Failed to fetch article details for {link}: {e}")
                continue
                
        return crawled_data

    async def run_crawling(self, start_page: int, max_pages: int, delay_per_article: float = 2.0):
        """
        지정된 범위의 페이지를 순회하며 DB에 기사를 적재합니다.
        """
        async with httpx.AsyncClient(headers=self.headers, timeout=20.0) as client:
            for page in range(start_page, start_page + max_pages):
                articles = await self.crawl_oilprice_page(client, page, delay=delay_per_article)
                if not articles:
                    break
                
                # DB 저장
                upsert_count = await self.db.upsert_news_articles(articles)
                logger.info(f"[ArchiveCrawler] Page {page} completed. Upserted {upsert_count} articles.")
                
                # 페이지 단위 딜레이
                await asyncio.sleep(delay_per_article * 2)
