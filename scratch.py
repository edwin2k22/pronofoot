import sqlite3

conn = sqlite3.connect('collector/data/zcode.db')
c = conn.cursor()
c.execute("SELECT date, status, referee_name FROM match_schedule WHERE home_team='Uruguay' AND away_team='Cape Verde'")
print(c.fetchone())
