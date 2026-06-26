"""
Debug script — teste le NLP momentum sur un match LIVE réel.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

from collector.sources import espn_stats
from collector.models import nlp_momentum as nlpm

# Matchs LIVE connus
TESTS = [("Turkey", "USA"), ("Paraguay", "Australia")]

for home, away in TESTS:
    print(f"\n=== {home} vs {away} ===")
    try:
        ev = espn_stats.find_event(home, away)
        print(f"  ESPN event: {ev}")
        if ev:
            tl = espn_stats.get_timeline(ev["id"])
            comments = tl.get("commentary", [])
            print(f"  Commentaires ESPN: {len(comments)}")
            if comments:
                print(f"  Dernier: {comments[-1]}")
            sig = nlpm.analyse_commentary(comments, home, away, current_minute=80)
            print(f"  homeMomentum={sig.home_momentum}  awayMomentum={sig.away_momentum}")
            print(f"  dominance={sig.dominance}  signals={len(sig.signals)}")
        else:
            print("  ❌ Match non trouvé sur ESPN")
    except Exception as e:
        import traceback
        print(f"  ❌ ERREUR: {e}")
        traceback.print_exc()
