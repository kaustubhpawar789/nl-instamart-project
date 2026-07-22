import json, urllib.request
body = {
  "respondent_name": "Test User",
  "email": "test@example.com",
  "city": "Mumbai",
  "age_group": "25-34",
  "order_frequency": "Daily",
  "categories": ["groceries"],
  "blockers": ["Always showing same products"],
  "suggestion": "Test suggestion"
}
req = urllib.request.Request("http://localhost:8080/api/survey/submit", 
                             data=json.dumps(body).encode(), 
                             headers={'Content-Type': 'application/json'})
try:
    res = urllib.request.urlopen(req)
    print("Response:", res.read().decode())
except urllib.error.HTTPError as e:
    print("Error:", e.code, e.read().decode())
