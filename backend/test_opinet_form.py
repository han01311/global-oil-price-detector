import httpx
import re

def test():
    url = "https://www.opinet.co.kr/glopcoilSelect.do"
    res = httpx.get(url)
    html = res.text
    
    # print the form tag and hidden inputs
    match = re.search(r'<form[^>]*name="form2".*?</form>', html, re.DOTALL)
    if not match:
        match = re.search(r'<form.*?name=".*?form.*?.*?</form>', html, re.DOTALL)
        
    if match:
        print("Form:\n", match.group(0))
        
    print("All inputs:")
    inputs = re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', html)
    print(inputs)

test()
