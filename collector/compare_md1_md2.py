import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector.models import best_picks

def evaluate_matchday(data, target_md):
    played_count = {}
    matches = []
    
    for m in sorted(data, key=lambda x: x.get('date', '')):
        home, away = m['home'], m['away']
        n = max(played_count.get(home, 0), played_count.get(away, 0)) + 1
        played_count[home] = n
        played_count[away] = n
        if n == target_md and m['status'] == 'FINISHED' and 'analysis' in m:
            matches.append(m)
            
    total = len(matches)
    if total == 0:
        return None
        
    w1N2 = sum(1 for m in matches if m['analysis']['predictionCorrect'])
    exact_scores = sum(1 for m in matches if m['analysis']['exactScore'])
    
    over25_ok = 0
    btts_ok = 0
    
    locks_proposed = 0
    locks_won = 0
    
    corners_total = 0
    corners_ok = 0
    cards_total = 0
    cards_ok = 0
    
    for m in matches:
        a = m['analysis']
        p = m['prediction']
        
        # O/U 2.5
        pred_over = p['over25'] >= 0.5
        real_over = a['over25Real']
        if pred_over == real_over:
            over25_ok += 1
            
        # BTTS
        pred_btts = p['btts'] >= 0.5
        real_btts = a['bttsReal']
        if pred_btts == real_btts:
            btts_ok += 1
            
        # Locks
        candidates = best_picks.candidate_picks(m)
        for pk in candidates:
            tier = best_picks.tier_of(pk['prob'], best_picks.TIERS, pk['market'])
            if tier == 'lock':
                won = best_picks._pick_won(pk['market'], pk['label'], m)
                if won is not None:
                    locks_proposed += 1
                    if won:
                        locks_won += 1
                        
        # Corners
        real_corners = (a.get('homeCorners') or 0) + (a.get('awayCorners') or 0) if a.get('homeCorners') is not None else None
        pred_corners_line = p.get('corners', {}).get('line')
        pred_corners_over = p.get('corners', {}).get('over', 0) >= 0.5
        if real_corners is not None and pred_corners_line is not None:
            corners_total += 1
            if (real_corners > pred_corners_line) == pred_corners_over:
                corners_ok += 1
                
        # Cards
        real_cards = (a.get('homeCards') or 0) + (a.get('awayCards') or 0) if a.get('homeCards') is not None else None
        pred_cards_line = p.get('cards', {}).get('line')
        pred_cards_over = p.get('cards', {}).get('over', 0) >= 0.5
        if real_cards is not None and pred_cards_line is not None:
            cards_total += 1
            if (real_cards > pred_cards_line) == pred_cards_over:
                cards_ok += 1
                
    return {
        'total': total,
        'w1N2': w1N2,
        'exact': exact_scores,
        'over25_ok': over25_ok,
        'btts_ok': btts_ok,
        'locks_proposed': locks_proposed,
        'locks_won': locks_won,
        'corners_total': corners_total,
        'corners_ok': corners_ok,
        'cards_total': cards_total,
        'cards_ok': cards_ok
    }

def main():
    data = json.load(open('collector/data/predictions.json', encoding='utf-8'))
    md1 = evaluate_matchday(data, 1)
    md2 = evaluate_matchday(data, 2)
    
    print("COMPARATIVE STUDY (MD1 vs MD2):")
    for md_num, stats in [(1, md1), (2, md2)]:
        if stats:
            print(f"\n--- JOURNÉE {md_num} ({stats['total']} matchs) ---")
            print(f"1N2 (Issue) : {stats['w1N2']}/{stats['total']} ({stats['w1N2']/stats['total']*100:.1f}%)")
            print(f"Scores Exacts : {stats['exact']}/{stats['total']} ({stats['exact']/stats['total']*100:.1f}%)")
            print(f"Over/Under 2.5 : {stats['over25_ok']}/{stats['total']} ({stats['over25_ok']/stats['total']*100:.1f}%)")
            print(f"BTTS : {stats['btts_ok']}/{stats['total']} ({stats['btts_ok']/stats['total']*100:.1f}%)")
            if stats['locks_proposed'] > 0:
                print(f"Locks 🔒 : {stats['locks_won']}/{stats['locks_proposed']} ({stats['locks_won']/stats['locks_proposed']*100:.1f}%)")
            if stats['corners_total'] > 0:
                print(f"Corners O/U : {stats['corners_ok']}/{stats['corners_total']} ({stats['corners_ok']/stats['corners_total']*100:.1f}%)")
            if stats['cards_total'] > 0:
                print(f"Cartons O/U : {stats['cards_ok']}/{stats['cards_total']} ({stats['cards_ok']/stats['cards_total']*100:.1f}%)")

if __name__ == '__main__':
    main()
