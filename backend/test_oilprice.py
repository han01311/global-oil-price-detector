import asyncio
import httpx
from bs4 import BeautifulSoup

async def main():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
        resp = await client.get("https://oilprice.com/Energy/Crude-Oil/Page-1.html")
        print(f"Status: {resp.status_code}")
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        articles = soup.find_all('div', class_='categoryArticle')
        print(f"Found {len(articles)} articles.")
        
        if articles:
            link = articles[0].find('a')['href'] if articles[0].find('a') else None
            print(f"First link: {link}")
            if link:
                a_resp = await client.get(link)
                a_soup = BeautifulSoup(a_resp.text, 'html.parser')
                title = a_soup.find('h1').text.strip() if a_soup.find('h1') else 'No title'
                date_span = a_soup.find('span', class_='article_byline')
                print(f"Title: {title}")
                print(f"Date line: {date_span.text if date_span else 'No date'}")

if __name__ == '__main__':
    asyncio.run(main())
