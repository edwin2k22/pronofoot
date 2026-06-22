import sqlite3
import json

conn = sqlite3.connect('C:/Users/zakro/ZCodeProject/collector/db/pronofoot.db')
conn.row_factory = sqlite3.Row

matches = conn.execute("SELECT id, home, away, status FROM matches WHERE home='France' OR home='Norway' OR home='Argentina'").fetchall()
for m in matches:
    print(dict(m))

    analysis = conn.execute("SELECT analysis_json FROM match_predictions WHERE match_id = ?", (m['id'],)).fetchone()
    if analysis and analysis['analysis_json']:
        data = json.loads(analysis['analysis_json'])
        print("Referee in analysis:", data.get('referee', 'N/A'))
