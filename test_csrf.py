import requests
import re
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

r = requests.get('https://juriscassation.cspj.ma/Decisions/RechercheDecisions', headers={'User-Agent': 'Mozilla/5.0'}, verify=False)
m = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', r.text)
if m:
    print("Token found:", m.group(1)[:20] + "...")
else:
    print("Token not found.")
