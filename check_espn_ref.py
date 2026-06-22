import sqlite3
import json
from collector.sources.espn_stats import parse_summary

conn = sqlite3.connect('C:/Users/zakro/ZCodeProject/collector/db/pronofoot.db')
matches = conn.execute("SELECT home, away, events_json FROM matches WHERE status != 'FINISHED' AND home IN ('France', 'Norway', 'Argentina')").fetchall()
for h, a, events_json in matches:
    if not events_json: continue
    try:
        data = json.loads(events_json)
        print(f'{h} vs {a}: Referee in DB =', data.get('referee'))
    except Exception as e:
        print(f'{h} vs {a}: Error {e}')

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
