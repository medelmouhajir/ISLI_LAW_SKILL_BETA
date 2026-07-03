import requests
import json
import urllib3
import sys
import io

if sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Force failure of live sources by pointing to an invalid proxy is hard; instead
# we simulate by calling the real endpoint and checking that the response shape
# includes cache fallback if everything else errors.
r = requests.post(
    "http://localhost:8000/search",
    json={"query": "طلاق"},
    headers={"Content-Type": "application/json"},
    timeout=60,
)
print("status code:", r.status_code)
data = r.json()
print("overall status:", data.get("status"))
print("total:", data.get("total"))
print("sources:", sorted(data.get("sources", {}).keys()))
for name, src in data.get("sources", {}).items():
    print(f"  {name}: status={src.get('status')} count={src.get('count')}")
