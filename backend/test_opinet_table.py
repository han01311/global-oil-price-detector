import httpx
import re

def test():
    url = "https://www.opinet.co.kr/glopcoilSelect.do"
    res = httpx.get(url)
    html = res.text
    
    # Extract the table body
    tbody_match = re.search(r'<tbody>(.*?)</tbody>', html, re.DOTALL)
    if tbody_match:
        tbody = tbody_match.group(1)
        rows = re.findall(r'<tr>(.*?)</tr>', tbody, re.DOTALL)
        for i, row in enumerate(rows[:5]):
            cols = re.findall(r'<td.*?>(.*?)</td>', row, re.DOTALL)
            # clean up tags
            cols = [re.sub(r'<[^>]+>', '', c).strip() for c in cols]
            print(f"Row {i}: {cols}")
    else:
        print("No tbody found")

test()
