import sys
sys.path.insert(0, 'c:\\Users\\zakro\\ZCodeProject')
from collector.db import database as db
conn = db.connect()
conn.execute("""
UPDATE matches
SET home_shots = 20, away_shots = 9,
    home_corners = 6, away_corners = 4,
    home_cards = 0, away_cards = 0
WHERE home = 'Switzerland' AND away = 'Jordan' AND utc_date = '2026-05-31 18:00 UTC'
""")
conn.commit()
print("Stats updated.")
