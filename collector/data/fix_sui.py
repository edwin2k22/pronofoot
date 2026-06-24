import sys
sys.path.insert(0, 'c:\\Users\\zakro\\ZCodeProject')
from collector.db import database as db
conn = db.connect()
conn.execute("INSERT INTO matches (home, away, status, utc_date, home_goals, away_goals) VALUES ('Switzerland', 'Jordan', 'FINISHED', '2026-05-31 18:00 UTC', 4, 1)")
conn.commit()
print("Match inserted.")
