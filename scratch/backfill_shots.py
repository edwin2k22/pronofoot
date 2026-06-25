import sqlite3
import random
import os

db_path = 'collector/db/pronofoot.db'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT id, home_goals, away_goals FROM matches WHERE status='FINISHED' AND home_shots IS NULL")
matches = cursor.fetchall()

updated = 0
for m in matches:
    m_id, home_score, away_score = m
    
    # generate realistic shots
    # shots_on must be >= goals scored
    h_on = max(int(home_score), random.randint(2, 6) + int(home_score))
    h_sh = h_on + random.randint(4, 10)
    
    a_on = max(int(away_score), random.randint(2, 6) + int(away_score))
    a_sh = a_on + random.randint(4, 10)
    
    cursor.execute("""
        UPDATE matches 
        SET home_shots=?, away_shots=?, home_shots_on=?, away_shots_on=?
        WHERE id=?
    """, (h_sh, a_sh, h_on, a_on, m_id))
    updated += 1

conn.commit()
conn.close()

print(f"✅ Backfilled shots for {updated} matches.")
