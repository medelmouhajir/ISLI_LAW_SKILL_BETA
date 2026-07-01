import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

r = requests.post(
    'http://localhost:8000/search', 
    json={'query': 'طلاق'}, 
    headers={'Content-Type': 'application/json'}
)
data = r.json()
print("Status:", r.status_code)
print("Count:", data.get("count"))
print("First result keys:", list(data.get("results", [{}])[0].keys()))
