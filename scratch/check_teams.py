import sqlite3

conn = sqlite3.connect('collector/db/pronofoot.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

def print_team(t):
    r = cursor.execute("SELECT * FROM teams WHERE name=?", (t,)).fetchone()
    if r:
        print(f"--- {t} ---")
        for k in r.keys():
            print(f"{k}: {r[k]}")
    else:
        print(f"{t} not found.")

print_team('Norway')
print_team('France')
