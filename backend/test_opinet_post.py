import httpx
import re

def test():
    url = "https://www.opinet.co.kr/glopcoilSelect.do"
    # Try doing a simple POST or GET with some query params?
    res = httpx.post(url, data={"TERM_W": "D", "STA_Y": "2024", "STA_M": "01", "STA_D": "01", "END_Y": "2024", "END_M": "01", "END_D": "31"})
    html = res.text
    
    # Just look for <tbody> since it wasn't there before
    match = re.search(r'<tbody[^>]*>(.*?)</tbody>', html, re.DOTALL)
    if match:
        tbody = match.group(1)
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody, re.DOTALL)
        for i, row in enumerate(rows[:5]):
            cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            cols = [re.sub(r'<[^>]+>', '', c).strip() for c in cols]
            print(f"Row {i}: {cols}")
    else:
        print("No tbody found")

test()
