import httpx
import re

def test():
    url = "https://www.opinet.co.kr/glopcoilSelect.do"
    # To get USD, the param might be UNIT=1 or CURRENCY=USD etc. Let's see the HTML form fields.
    res = httpx.get(url)
    html = res.text
    inputs = re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', html)
    print("Default Inputs:", set(inputs))
    
    # Try POST with USD currency
    data = {
        "TERM_D": "D", # D for Daily, W for Weekly
        "UNIT": "1", # 1 for USD?
        "CURR": "1",
        "UNIT_1": "1",
        "WONI": "1"
    }
    res = httpx.post(url, data=data)
    match = re.search(r'<tbody[^>]*>(.*?)</tbody>', res.text, re.DOTALL)
    if match:
        tbody = match.group(1)
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody, re.DOTALL)
        for i, row in enumerate(rows[:2]):
            cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            cols = [re.sub(r'<[^>]+>', '', c).strip() for c in cols]
            print(f"Row {i}: {cols}")
    else:
        print("No tbody found")

test()
