import requests
import json
import urllib3
import sys
import io
from bs4 import BeautifulSoup
from urllib.parse import quote

if sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

for query in ["divorce", "cassation", "طلاق"]:
    print(f"\n=== Query: {query} ===")
    url = f"https://adala.justice.gov.ma/search?term={quote(query)}&type=rapid_search"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, verify=False, timeout=15)
    print(f"Status: {r.status_code}")
    soup = BeautifulSoup(r.text, "html.parser")
    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data and next_data.string:
        try:
            data = json.loads(next_data.string)
            search_res = data.get("props", {}).get("pageProps", {}).get("searchResult", {})
            if isinstance(search_res, dict):
                print(f"total: {search_res.get('total')}")
                items = search_res.get("data", [])
                print(f"items: {len(items)}")
                for item in items[:2]:
                    print(f"  - {item.get('title') or item.get('name')}")
        except Exception as e:
            print(f"Parse error: {e}")
    else:
        print("No __NEXT_DATA__")
