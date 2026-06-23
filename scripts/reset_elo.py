"""Réinitialise les ratings Elo et moyennes d'équipes (et l'historique).

Utilitaire de maintenance : à lancer depuis la RACINE du projet, pas depuis scripts/ :

    python3 scripts/reset_elo.py
"""
import sqlite3
from collector.sources.team_ratings import get_rating
from collector.pipeline import PRIOR

def reset_db():
    conn = sqlite3.connect('collector/db/pronofoot.db')
    
    # Reset team elos and averages
    teams = conn.execute("SELECT name FROM teams").fetchall()
    for (name,) in teams:
        r = get_rating(name)
        conn.execute("""
            UPDATE teams 
            SET elo=?, fifa_prior=?, matches_played=0,
                gf_avg=?, ga_avg=?, xg_avg=?, xga_avg=?
            WHERE name=?
        """, (r, r, PRIOR["gf"], PRIOR["ga"], PRIOR["xg"], PRIOR["xg"], name))
        
    # Reset matches to unprocessed
    conn.execute("UPDATE matches SET processed=0 WHERE status='FINISHED'")
    
    # Clear history
    conn.execute("DELETE FROM rating_history")
    
    conn.commit()
    conn.close()
    print("Database reset complete.")

if __name__ == '__main__':
    reset_db()
