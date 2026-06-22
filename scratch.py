import sqlite3
import json

conn = sqlite3.connect('collector/db/pronofoot.db')
c = conn.cursor()
c.execute("SELECT fouls_avg, matches_played FROM teams WHERE name='Uruguay' OR name='Cape Verde'")
print(c.fetchall())
