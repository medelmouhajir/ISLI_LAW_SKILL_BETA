import requests
import json
import urllib3
import sys
import io

if sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

r = requests.post(
    "http://localhost:8000/search",
    json={"query": "طلاق", "chamber_id": 2},
    headers={"Content-Type": "application/json"},
    timeout=60,
)
r.raise_for_status()
data = r.json()

print("Top-level keys:", sorted(data.keys()))
print("status:", data.get("status"))
print("query:", data.get("query"))
print("count:", data.get("count"))
print("total:", data.get("total"))
print("results length:", len(data.get("results", [])))
print("sources keys:", sorted(data.get("sources", {}).keys()))

if data.get("results"):
    print("\nFirst flat result:")
    print(json.dumps(data["results"][0], ensure_ascii=False, indent=2))
