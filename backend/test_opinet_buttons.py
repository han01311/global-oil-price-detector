import httpx
import re

def test():
    url = "https://www.opinet.co.kr/glopcoilSelect.do"
    res = httpx.get(url)
    html = res.text
    
    # search for dollar symbol or won symbol in a link
    matches = re.findall(r'<a[^>]*>\s*(?:\[\$\]|\[원\]|&#36;)\s*</a>', html, re.IGNORECASE)
    print("Found links:", matches)
    
    # Or just search for javascript calls
    matches2 = re.findall(r'<a[^>]*href="javascript:[^"]*"[^>]*>', html)
    for m in matches2:
        if "fn_" in m or "go" in m or "change" in m:
            print("JS Link:", m)

test()
