import requests
import re
import urllib3
import sys
import io
from bs4 import BeautifulSoup

if sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://juriscassation.cspj.ma"

session = requests.Session()
session.verify = False
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
})

# Get CSRF token
r = session.get(f"{BASE}/Decisions/RechercheDecisions", timeout=15)
r.raise_for_status()
m = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', r.text)
token = m.group(1) if m else None
print("Token found:", bool(token))

if not token:
    raise SystemExit("No CSRF token")

# Search for divorce
data = {
    "NumeroDos": "",
    "NumeroDec": "",
    "DateDec": "",
    "ChambreIds": "2",
    "DecisionPriseParId": "",
    "Sujet": "طلاق",
    "__RequestVerificationToken": token,
}

r = session.post(
    f"{BASE}/Decisions/RechercheDecisionsRes",
    data=data,
    timeout=20,
    headers={
        "Referer": f"{BASE}/Decisions/RechercheDecisions",
        "Origin": BASE,
        "Content-Type": "application/x-www-form-urlencoded",
    },
)
r.raise_for_status()

soup = BeautifulSoup(r.text, "html.parser")

# Show all table IDs/classes and first few rows
print("\n=== Tables ===")
for i, table in enumerate(soup.find_all("table")):
    print(f"table {i}: id={table.get('id')}, class={table.get('class')}")
    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    if headers:
        print("  headers:", headers)
    rows = table.find_all("tr")
    print(f"  rows: {len(rows)}")
    for j, tr in enumerate(rows[:2]):
        tds = [td.get_text(strip=True)[:120] for td in tr.find_all("td")]
        print(f"    row {j}: {tds}")

# Show all GetArret links
print("\n=== GetArret links ===")
for a in soup.find_all("a", href=re.compile(r"GetArret"))[:5]:
    print(a.get("href"), a.get_text(strip=True)[:80])
