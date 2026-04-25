import httpx
import re

def test():
    url = "https://www.opinet.co.kr/glopcoilSelect.do"
    res = httpx.get(url)
    html = res.text
    
    # search for dollar symbol or won symbol in a link
    matches = re.findall(r'<a[^>]*>(.*?)</a>', html, re.IGNORECASE)
    for m in matches:
        if "$" in m or "원" in m:
            print("Found link content:", m)

test()
