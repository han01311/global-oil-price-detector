import httpx
import pandas as pd
from io import StringIO

def test():
    url = "https://www.opinet.co.kr/glopcoilSelect.do"
    res = httpx.get(url)
    
    tables = pd.read_html(StringIO(res.text))
    print(f"Found {len(tables)} tables")
    for i, table in enumerate(tables):
        print(f"\n--- Table {i} ---")
        print(table.head())

test()
