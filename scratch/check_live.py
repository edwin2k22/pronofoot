import sqlite3, json

conn = sqlite3.connect('collector/db/pronofoot.db')
conn.row_factory = sqlite3.Row

# Check live matches in DB
rows = conn.execute("SELECT home, away, status FROM matches WHERE status IN ('LIVE','HT')").fetchall()
print("=== LIVE dans la base ===")
for r in rows:
    print(dict(r))

# Check predictions.json
with open('collector/data/predictions.json', encoding='utf-8') as f:
    preds = json.load(f)

print("\n=== LIVE dans predictions.json ===")
for m in preds:
    if m.get('status') in ('LIVE', 'HT'):
        nlp = m.get('nlpMomentum')
        print(f"  {m['home']} vs {m['away']}  | nlpMomentum: {nlp}")
