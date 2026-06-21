import json
import sys
from collector.models.best_picks import candidate_picks, tier_of, _pick_won, TIERS

sys.stdout.reconfigure(encoding='utf-8')

with open('collector/data/predictions.json', encoding='utf-8') as f:
    matches = json.load(f)

print('| Match | Résultat Réel | Pick (Sécurisé / Lock) | Confiance | Résultat |')
print('|---|---|---|---|---|')

wins = 0
losses = 0

for m in matches:
    if m.get('status') != 'FINISHED' or not m.get('analysis'): continue
    
    a = m['analysis']
    try:
        hg, ag = map(int, a['realScore'].split('-'))
    except Exception:
        continue
    
    # Check all candidate picks for this match
    candidates = candidate_picks(m)
    for pk in candidates:
        tier = tier_of(pk['prob'], TIERS, pk['market'])
        if tier == 'lock': # Highest confidence
            won = _pick_won(pk['market'], pk['label'], m)
            if won is None: continue
            
            if won: wins += 1
            else: losses += 1
            
            res_icon = '✅ Gagné' if won else '❌ Perdu'
            print(f'| {m["home"]} vs {m["away"]} | {a["realScore"]} | {pk["market"]} - {pk["label"]} | {pk["prob"]*100:.1f}% | {res_icon} |')

print(f'\nTotal Meilleurs Choix (Lock): {wins} gagnés, {losses} perdus ({(wins/(wins+losses)*100) if wins+losses>0 else 0:.1f}% de réussite)')
