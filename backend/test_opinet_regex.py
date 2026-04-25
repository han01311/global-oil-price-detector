import httpx
import re

def test():
    url = "https://www.opinet.co.kr/glopcoilSelect.do"
    res = httpx.get(url)
    html = res.text
    
    # Just print lines that contain "Dubai" or "WTI" to see if data is inline
    lines = html.split('\n')
    for i, line in enumerate(lines):
        if "Dubai" in line or "WTI" in line:
            print(f"Line {i}: {line.strip()}")

test()
