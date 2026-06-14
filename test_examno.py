import requests
import json

base_url = "https://studentportal.universitysolutions.in/src/results_new.php"
regno = "01JST25UCS134"

actions = ["getExamno", "getExamList", "getExams", "getPrevExamno", "getAllExamno"]

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/114.0.0.0",
    "Accept": "application/json, text/plain, */*",
})

for a in actions:
    url = f"{base_url}?a={a}&regno={regno}"
    try:
        r = session.get(url, timeout=10)
        print(f"Action: {a} -> Status: {r.status_code}")
        try:
            print(json.dumps(r.json())[:500])
        except:
            print(r.text[:500])
    except Exception as e:
        print(f"Action: {a} -> Error: {e}")
    print("-" * 40)
