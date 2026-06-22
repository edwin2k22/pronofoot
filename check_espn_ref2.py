import requests
import json

url = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
r = requests.get(url)
data = r.json()
for event in data.get('events', []):
    name = event['name']
    competitions = event.get('competitions', [{}])
    ref = None
    for off in competitions[0].get('officials', []):
        if (off.get('position', {}).get('name', '').lower() == 'referee'):
            ref = off.get('fullName')
    print(f"ESPN Scoreboard {name}: Referee = {ref}")
