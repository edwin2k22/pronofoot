import json
import sqlite3
import os

def test():
    with open('collector/data/match_events_real.json', encoding="utf-8") as f:
        events = json.load(f)
    
    key = "Brazil|Japan"
    ev = dict(events.get(key) or {})
    ev_json = json.dumps(ev, ensure_ascii=False) if ev else None
    
    db_path = os.path.join('collector', 'db', 'pronofoot.db')
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE matches SET events_json=? WHERE home='Brazil' AND away='Japan'", (ev_json,))
    conn.commit()
    
    c = conn.execute("SELECT events_json FROM matches WHERE home='Brazil' AND away='Japan'").fetchone()
    print("DB now has goals?", 'goals' in c[0])
    conn.close()

test()
