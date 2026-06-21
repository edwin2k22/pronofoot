import sqlite3
c = sqlite3.connect('collector/db/pronofoot.db')
for r in c.execute("SELECT name, elo FROM teams WHERE name IN ('Spain', 'Saudi Arabia')"):
    print(r)
