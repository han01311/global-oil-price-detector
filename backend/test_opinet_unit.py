import httpx
import re

def test():
    url = "https://www.opinet.co.kr/glopcoilSelect.do"
    # Try different values for UNIT or others
    for u in ["1", "2", "3", "0", "$", "BBL", "bbl"]:
        res = httpx.post(url, data={"TERM_D": "D", "UNIT": u, "CURR": u, "UNIT_1": u})
        html = res.text
        match = re.search(r'<tbody[^>]*>(.*?)</tbody>', html, re.DOTALL)
        if match:
            tbody = match.group(1)
            row = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody, re.DOTALL)[0]
            cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            cols = [re.sub(r'<[^>]+>', '', c).strip() for c in cols]
            print(f"U={u}: {cols}")

test()
