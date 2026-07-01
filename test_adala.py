import requests
from bs4 import BeautifulSoup
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

r = requests.get('https://adala.justice.gov.ma/search?term=طلاق&type=rapid_search', headers={'User-Agent': 'Mozilla/5.0'}, verify=False)
soup = BeautifulSoup(r.text, 'html.parser')

next_data = soup.find('script', id='__NEXT_DATA__')
if next_data:
    data = json.loads(next_data.string)
    print("Found __NEXT_DATA__! Keys in props:", data.get('props', {}).keys())
    # Try to find the pageProps
    page_props = data.get('props', {}).get('pageProps', {})
    search_res = page_props.get('searchResult', {})
    if isinstance(search_res, dict):
        print("searchResult total:", search_res.get('total'))
        items = search_res.get('data', [])
        print("data length:", len(items))
        if items and isinstance(items, list):
            print("First item keys:", items[0].keys())
            print("First item sample:", {k: items[0][k] for k in list(items[0].keys())[:5]})
else:
    print("No __NEXT_DATA__ found.")
    print("HTML excerpt:", r.text[:500])
