"""
Debug script - saves all raw API responses to debug_output.txt
Run: python debug_fetch.py
Then share debug_output.txt
"""
import json, requests, sys

BASE = "https://studentportal.universitysolutions.in"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/x-www-form-urlencoded",
}

mobile   = input("Mobile/Reg No: ").strip()
password = input("Password: ").strip()

s = requests.Session()
s.headers.update(HEADERS)
out = []

def log(title, text):
    line = f"\n{'='*60}\n{title}\n{'='*60}\n{text}\n"
    print(line)
    out.append(line)

# 1. Login
r = s.post(f"{BASE}/signin.php", data={"regno": mobile, "passwd": password}, timeout=30)
log("LOGIN", r.text)

# 2. Profile
r = s.post(f"{BASE}/src/profile.php", timeout=30)
log("PROFILE (full)", r.text)

# 3. Old exam list
r = s.get(f"{BASE}/src/old_results.php?a=getExamno", timeout=30)
log("OLD EXAM LIST", r.text)

# 4. New exam list
r = s.get(f"{BASE}/src/results_new.php?a=getExamno", timeout=30)
log("NEW EXAM LIST", r.text)

# Try to parse exam list
try:
    j = json.loads(r.text[r.text.find("{"):r.text.rfind("}")+1])
    rows = j.get("data") or []
except:
    rows = []

# 5. Try every action name with every examno we can find
actions = ["getResDet", "getResults", "getSubMarks", "getmarks", "getdetails", "getResult", "getMarks"]

for row in rows:
    log("EXAM ROW KEYS", str(row))
    for k, v in row.items():
        examno = str(v)
        for action in actions:
            url = f"{BASE}/src/results_new.php?a={action}&examno={examno}"
            try:
                r2 = s.get(url, timeout=15)
                log(f"results_new.php a={action} examno={examno} ({len(r2.text)}b)", r2.text[:500])
            except Exception as e:
                log(f"results_new.php a={action} examno={examno} ERROR", str(e))

        for action in actions:
            url = f"{BASE}/src/old_results.php?a={action}&examno={examno}"
            try:
                r2 = s.get(url, timeout=15)
                log(f"old_results.php a={action} examno={examno} ({len(r2.text)}b)", r2.text[:500])
            except Exception as e:
                log(f"old_results.php a={action} examno={examno} ERROR", str(e))

# Also try without examno
for action in actions:
    url = f"{BASE}/src/results_new.php?a={action}"
    try:
        r2 = s.get(url, timeout=15)
        log(f"results_new.php a={action} NO-EXAMNO ({len(r2.text)}b)", r2.text[:500])
    except Exception as e:
        log(f"ERROR", str(e))

# Save to file
with open("debug_output.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))

print("\n\n✅ Saved to debug_output.txt — please share that file!")
