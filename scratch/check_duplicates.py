import sqlite3
import os

db_path = os.path.join('collector', 'db', 'pronofoot.db')
c = sqlite3.connect(db_path)
rows = c.execute("SELECT id, status FROM matches WHERE home='Brazil' AND away='Japan'").fetchall()
print(rows)
