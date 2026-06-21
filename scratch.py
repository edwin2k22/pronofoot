import json
import sys
from collector.models.best_picks import candidate_picks, _pick_won, _real_total

sys.stdout.reconfigure(encoding='utf-8')

with open('collector/data/predictions.json', encoding='utf-8') as f:
    matches = json.load(f)

for m in matches:
    if m.get('home') == 'Belgium' and m.get('away') == 'Iran':
        print("Match found:", m.get('status'))
        a = m.get('analysis')
        if a:
            print(f"Real Shots: Home {a.get('homeShots')}, Away {a.get('awayShots')}")
            real = _real_total('TIRS', a)
            print("Total real shots computed:", real)
        
        cands = candidate_picks(m)
        tirs_cands = [c for c in cands if c['market'] == 'TIRS']
        print("TIRS candidates:", tirs_cands)
        for c in tirs_cands:
            won = _pick_won(c['market'], c['label'], m)
            print("Pick Won:", won)
