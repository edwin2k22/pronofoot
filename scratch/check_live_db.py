import sqlite3
c=sqlite3.connect('collector/db/pronofoot.db')
print(c.execute("SELECT home, away, status, live_clock FROM matches WHERE status='LIVE'").fetchall())
