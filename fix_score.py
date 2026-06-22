import sqlite3
import json

db_path = 'C:/Users/zakro/ZCodeProject/collector/db/pronofoot.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT id, home, away, home_goals, away_goals, status, events_json FROM matches WHERE home LIKE '%Belgium%' OR away LIKE '%Belgium%'").fetchall()

for r in rows:
    if 'Iran' in r['home'] or 'Iran' in r['away']:
        print(f"Match found: {r['home']} vs {r['away']}, Score: {r['home_goals']}-{r['away_goals']}")
        print(f"Events: {r['events_json']}")
        
        # update goals
        home_goals = 0
        away_goals = 0
        
        # remove goals from events
        events = json.loads(r['events_json']) if r['events_json'] else {}
        if 'goals' in events:
            events['goals'] = []
            
        conn.execute("UPDATE matches SET home_goals=?, away_goals=?, events_json=? WHERE id=?", 
                     (home_goals, away_goals, json.dumps(events), r['id']))
        print("Updated to 0-0 and cleared goals.")

conn.commit()
conn.close()
