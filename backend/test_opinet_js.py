import httpx
import re

def test():
    url = "https://www.opinet.co.kr/glopcoilSelect.do"
    res = httpx.get(url)
    html = res.text
    
    scripts = re.findall(r'<script.*?>(.*?)</script>', html, re.DOTALL)
    for i, script in enumerate(scripts):
        if "goSubPage" in script or "ajax" in script.lower():
            print(f"Script {i}:\n{script[:500]}...\n")

test()
