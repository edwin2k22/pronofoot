import sys
sys.path.insert(0, 'c:\\Users\\zakro\\ZCodeProject')
from collector import pipeline
from collector.models import markets, best_picks, shrinkage
from collector.db import database as db

conn = db.init_db()
conn.row_factory = db.sqlite3.Row
matches = [dict(r) for r in conn.execute("SELECT * FROM matches")]
stats = {'win': 0, 'loss': 0, 'total': 0}
all_picks = []

for mt in matches:
    if mt['status'] != 'FINISHED' or mt['home_shots'] is None:
        continue
    
    h = db.get_team(conn, mt['home'])
    a = db.get_team(conn, mt['away'])
    
    sh_h = h['shots_avg'] if h['shots_avg'] else 12.0
    sh_a = a['shots_avg'] if a['shots_avg'] else 12.0
    son_h = h['shots_on_avg'] if h['shots_on_avg'] else 4.2
    son_a = a['shots_on_avg'] if a['shots_on_avg'] else 4.2
    
    sm = markets.shots_model(sh_h, sh_a, son_h, son_a)
    
    best = best_picks._best_ou_line(sm.get('lines', {}), 'tirs')
    if best and best['prob'] >= 0.72: # Threshold for Strong/Lock
        line = best_picks._extract_line(best['label'])
        real = mt['home_shots'] + mt['away_shots']
        is_over = 'Plus' in best['label']
        won = (real > line) if is_over else (real < line)
        
        if won: stats['win'] += 1
        else: stats['loss'] += 1
        stats['total'] += 1
        
        tier = best_picks.tier_of(best['prob'], best_picks.TIERS, 'TIRS')
        all_picks.append({
            'match': f"{mt['home']} vs {mt['away']}",
            'pick': best['label'],
            'prob': best['prob'],
            'won': won,
            'real': real,
            'tier': tier
        })

rate = (stats['win']/stats['total']*100) if stats['total'] > 0 else 0
print(f"Bilan TIRS (Strong/Lock) : {stats['win']} Gagnés / {stats['loss']} Perdus (Taux de réussite : {rate:.1f}%)")

print("Détail des paris Tirs perdants :")
for p in all_picks:
    if not p['won']:
        print(f"  - {p['match']} : Prédit {p['pick']} ({p['prob']:.0%} {p['tier']}) -> Réel: {p['real']} tirs")
