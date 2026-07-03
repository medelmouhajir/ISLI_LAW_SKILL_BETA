import requests
import json
import urllib3
import sys
import io

# Force UTF-8 for stdout on Windows so Arabic/French output prints correctly.
if sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "http://localhost:8000"

def call_search(payload):
    r = requests.post(
        f"{BASE}/search",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def print_result(data):
    print(f"\nQuery: {data.get('query')!r}")
    print(f"Overall status: {data.get('status')}")
    print(f"Total results: {data.get('total')}")
    for source, info in data.get("sources", {}).items():
        print(f"\n  [{source}] status={info.get('status')} count={info.get('count')}")
        if info.get("error"):
            print(f"    error: {info['error']}")
        for i, item in enumerate(info.get("results", [])[:3]):
            print(f"    result {i+1}: {json.dumps(item, ensure_ascii=False)[:300]}")
        if info.get("count", 0) > 3:
            print(f"    ... and {info['count'] - 3} more")


queries = [
    {"query": "طلاق"},
    {"query": "طلاق", "chamber_id": 2},
    {"query": "سرقة", "chamber_id": 6},
]

for q in queries:
    try:
        result = call_search(q)
        print_result(result)
    except Exception as e:
        print(f"\nFAILED for {q}: {e}")

print("\n--- health check ---")
try:
    r = requests.get(f"{BASE}/health", timeout=10)
    print(r.json())
except Exception as e:
    print(f"health check failed: {e}")
