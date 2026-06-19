#!/usr/bin/env python3
"""
Réactualisation AUTOMATIQUE en boucle — refresh régulier.

Relance `refresh` à intervalle régulier pour garder l'app à jour pendant le
tournoi (nouveaux résultats, ratings, effectifs). À lancer dans un terminal à part.

Usage :
    python3 -m collector.autorefresh                 # toutes les 5 min (défaut)
    python3 -m collector.autorefresh --interval 120  # toutes les 2 min
    python3 -m collector.autorefresh --once          # une seule passe

Astuce : combine avec le serveur web dans un autre terminal :
    python3 -m http.server 8077
"""
from __future__ import annotations
import sys, os, time, argparse, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import refresh


def main():
    ap = argparse.ArgumentParser(description="Refresh automatique CDM 2026")
    ap.add_argument("--interval", type=int, default=300, help="secondes entre refresh (défaut 300)")
    ap.add_argument("--once", action="store_true", help="une seule passe puis stop")
    args = ap.parse_args()

    n = 0
    while True:
        n += 1
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n{'='*52}\n🔄 Refresh #{n} — {ts}\n{'='*52}")
        try:
            refresh.main()
        except Exception as e:
            print(f"  [warn] refresh a échoué : {e} (on réessaiera)")
        if args.once:
            break
        print(f"\n⏳ Prochaine actualisation dans {args.interval}s "
              f"(Ctrl+C pour arrêter)...")
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n👋 Arrêt du refresh automatique.")
            break


if __name__ == "__main__":
    main()
