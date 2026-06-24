import sys
sys.path.insert(0, 'c:\\Users\\zakro\\ZCodeProject')
from collector.db import database as db
conn = db.connect()

print('--- Switzerland ---')
for row in conn.execute("SELECT home, away, home_goals, away_goals, utc_date FROM matches WHERE (home='Switzerland' OR away='Switzerland') AND status='FINISHED' ORDER BY utc_date DESC LIMIT 5"):
    print(dict(row))

print('--- Canada ---')
for row in conn.execute("SELECT home, away, home_goals, away_goals, utc_date FROM matches WHERE (home='Canada' OR away='Canada') AND status='FINISHED' ORDER BY utc_date DESC LIMIT 5"):
    print(dict(row))
