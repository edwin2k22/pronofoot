import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from models import best_picks

data = json.load(open('collector/data/predictions.json', encoding='utf-8'))

played_count = {}
matches_md2 = []

for m in sorted(data, key=lambda x: x.get('date', '')):
    home, away = m['home'], m['away']
    n = max(played_count.get(home, 0), played_count.get(away, 0)) + 1
    played_count[home] = n
    played_count[away] = n
    if n == 2 and m['status'] == 'FINISHED' and 'analysis' in m:
        matches_md2.append(m)

failed_locks = []
failed_others = []

for m in matches_md2:
    candidates = best_picks.candidate_picks(m)
    for pk in candidates:
        tier = best_picks.tier_of(pk['prob'], best_picks.TIERS, pk['market'])
        won = best_picks._pick_won(pk['market'], pk['label'], m)
        if won is False:
            info = {
                'match': f"{m['home']} vs {m['away']}",
                'score': m.get('analysis', {}).get('realScore', '?-?'),
                'pick': f"{pk['market']} - {pk['label']}",
                'prob': pk['prob'],
                'tier': tier
            }
            if tier == 'lock':
                failed_locks.append(info)
            else:
                failed_others.append(info)

print('FAILED LOCKS:')
for fl in failed_locks:
    print(fl)

print('\nFAILED OTHER BEST PICKS:')
for fo in failed_others:
    print(fo)
