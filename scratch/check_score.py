import sqlite3
import os

db_path = os.path.join('collector', 'db', 'pronofoot.db')
c = sqlite3.connect(db_path)
c.row_factory = sqlite3.Row
rows = c.execute("SELECT * FROM matches WHERE home='Brazil' AND away='Japan'").fetchall()
for r in rows:
    print(dict(r))
