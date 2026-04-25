import httpx
import re

def test():
    url = "https://www.opinet.co.kr/glopcoilSelect.do"
    res = httpx.get(url)
    html = res.text
    
    match = re.search(r'.{0,100}\[\$\].{0,100}', html, re.DOTALL | re.IGNORECASE)
    if match:
        print("Dollar link context:\n", match.group(0))

test()
