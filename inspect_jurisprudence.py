import requests
import urllib3
import sys
import io
from bs4 import BeautifulSoup

if sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

for query in ["cassation", "divorce", "طلاق"]:
    print(f"\n=== Query: {query} ===")
    r = requests.get(
        "https://www.jurisprudence.ma/",
        params={"s": query},
        headers={"User-Agent": "Mozilla/5.0"},
        verify=False,
        timeout=15,
    )
    print(f"Status: {r.status_code}, URL: {r.url}")
    soup = BeautifulSoup(r.text, "html.parser")
    articles = soup.find_all("article")
    print(f"article count: {len(articles)}")
    if not articles:
        articles = soup.find_all("div", class_=lambda c: c and any(x in c.lower() for x in ["post", "entry", "result"]))
        print(f"fallback div count: {len(articles)}")
    for i, article in enumerate(articles[:3]):
        title_tag = article.find(["h2", "h3"])
        if title_tag:
            link = title_tag.find("a")
            if link:
                print(f"  {i+1}. {link.get_text(strip=True)} -> {link.get('href')}")
