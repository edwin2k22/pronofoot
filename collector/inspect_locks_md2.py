import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector.models import best_picks

def main():
    data = json.load(open('collector/data/predictions.json', encoding='utf-8'))
    played_count = {}
    
    # Let's map matches by matchday
    md2_matches = []
    
    for m in sorted(data, key=lambda x: x.get('date', '')):
        home, away = m['home'], m['away']
        n = max(played_count.get(home, 0), played_count.get(away, 0)) + 1
        played_count[home] = n
        played_count[away] = n
        m['matchday'] = n
        if n == 2 and m['status'] == 'FINISHED':
            md2_matches.append(m)

    print(f"--- ANALYSE DES MEILLEURS CHOIX POUR LA JOURNÉE 2 ({len(md2_matches)} matchs) ---")
    
    total_proposed = 0
    total_won = 0
    
    for m in md2_matches:
        print(f"\n⚽ Match : {m['home']} vs {m['away']} (Score : {m['analysis']['realScore']})")
        # generate all picks that would have been candidates
        candidates = best_picks.candidate_picks(m)
        locks = []
        for pk in candidates:
            tier = best_picks.tier_of(pk['prob'], best_picks.TIERS, pk['market'])
            if tier == 'lock':
                won = best_picks._pick_won(pk['market'], pk['label'], m)
                locks.append((pk, won))
                
        if not locks:
            print("  (Aucun choix 'Verrouillé' / Lock identifié pour ce match)")
            continue
            
        for pk, won in locks:
            total_proposed += 1
            if won:
                total_won += 1
            status_str = "✅ GAGNÉ" if won else "❌ PERDU"
            print(f"  • [🔒 LOCK] {pk['label']} (prob: {pk['prob']:.2f}) -> {status_str}")
            
    print(f"\n--- BILAN DE LA JOURNÉE 2 ---")
    if total_proposed > 0:
        print(f"Total des Locks proposés : {total_proposed}")
        print(f"Locks gagnés : {total_won} / {total_proposed} ({total_won/total_proposed*100:.1f}%)")
    else:
        print("Aucun lock n'a été proposé pour ces matchs.")

if __name__ == '__main__':
    main()
