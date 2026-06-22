import requests
import json

url = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
r = requests.get(url)
data = r.json()
for event in data.get('events', []):
    name = event['name']
    if 'Argentina' in name or 'Austria' in name:
        status = event.get('status', {}).get('type', {}).get('name')
        competitors = event.get('competitions', [{}])[0].get('competitors', [])
        score = " - ".join([f"{c['team']['name']} {c.get('score', '?')}" for c in competitors])
        print(f"Match: {name} | Status: {status} | Score: {score}")
