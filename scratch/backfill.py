import sqlite3, json, os

db_path = 'collector/db/pronofoot.db'

import urllib.request
url = 'https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json'
with urllib.request.urlopen(url) as resp:
    data = json.loads(resp.read().decode('utf-8'))

conn = sqlite3.connect(db_path)
count = 0
for m in data.get('matches', []):
    ht = m.get('score', {}).get('ht')
    t1, t2 = m.get('team1'), m.get('team2')
    date = f"{m.get('date','')} {m.get('time','')}".strip()
    if ht and len(ht) == 2:
        row = conn.execute('SELECT id FROM matches WHERE home=? AND away=? AND utc_date=?', (t1, t2, date)).fetchone()
        if row:
            conn.execute('UPDATE matches SET home_ht_goals=?, away_ht_goals=? WHERE id=?', (ht[0], ht[1], row[0]))
            count += 1
conn.commit()
conn.close()
print(f'Backfilled HT scores for {count} matches.')
