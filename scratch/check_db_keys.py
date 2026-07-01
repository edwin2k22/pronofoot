import sqlite3, json, os

db_path = os.path.join('collector', 'db', 'pronofoot.db')
c = sqlite3.connect(db_path)
c.row_factory = sqlite3.Row
r = c.execute("SELECT events_json FROM matches WHERE home='Brazil' AND away='Japan'").fetchone()

if r and r['events_json']:
    ev = json.loads(r['events_json'])
    print("Keys in events_json:", list(ev.keys()))
    if 'goals' in ev:
        print("Goals:", len(ev['goals']))
else:
    print("No events_json")
