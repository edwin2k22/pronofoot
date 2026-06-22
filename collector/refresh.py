#!/usr/bin/env python3
"""
Réactualisation complète de l'app depuis le web — une seule commande.

Ce script va chercher lui-même les données fraîches dont l'app a besoin :
  1. télécharge le calendrier + résultats CDM 2026 à jour (openfootball)
  2. télécharge les effectifs 2026 à jour (openfootball squads)
  3. ré-applique les vrais ratings FIFA (figés au 11/06/2026 dans fifa_ranking.py)
  4. ingère les nouveaux résultats → met à jour Elo (anti-overreaction)
  5. régénère predictions.json + squads_2026.json pour l'app

Usage :
    python3 -m collector.refresh
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collector.http_cache import get_json
from collector import pipeline, player_ingest, live, embed, import_stats
from collector.sources import openfootball_wc, squads_2026

WC_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
SQUADS_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.squads.json"


def main():
    print("🌐 1/5 — calendrier & résultats CDM 2026 (openfootball)...")
    get_json(WC_URL, ttl=0)          # ttl=0 -> force le re-téléchargement
    sched = openfootball_wc.load_schedule(ttl=0)
    played = [m for m in sched.get("matches", []) if m.get("score", {}).get("ft")]
    print(f"   {len(sched.get('matches', []))} matchs, {len(played)} terminés.")

    print("🌐 2/5 — effectifs 2026 (openfootball squads)...")
    get_json(SQUADS_URL, ttl=0)
    sq = squads_2026.load_squads(ttl=0)
    print(f"   {len(sq)} sélections, {sum(len(t.get('players', [])) for t in sq)} joueurs.")

    print("⚙️  3/5 — seed (calendrier + vrais ratings FIFA + joueurs)...")
    db_path = os.path.join(os.path.dirname(__file__), "db", "pronofoot.db")
    for ext in ["", "-wal", "-shm"]:
        p = db_path + ext
        if os.path.exists(p):
            os.remove(p)
    pipeline.seed()

    print("🌐 Ingestion & statistiques des matchs amicaux de 2026...")
    from collector import import_friendlies
    import_friendlies.main()

    print("⚙️  4/5 — live temps réel + ingestion des résultats + mise à jour Elo...")
    try:
        live.auto_pull()               # worldcup26.ir : live scores temps réel
    except Exception as e:
        print(f"   [warn] live API indisponible ({e}), fallback openfootball.")
    live.sync_openfootball()           # filet de sécurité : scores finaux openfootball
    pipeline.ingest()
    try:
        from collector import espn_ingest
        espn_ingest.main()
        import_stats.main()            # vraies stats (xG/tirs/corners/cartons) des matchs finis
    except Exception as e:
        print(f"   [warn] import stats échoué : {e}")
    
    pipeline.update()                  # maj des moyennes (inclut possession, xG, fautes)

    # compos officielles des matchs à venir (XI réel ESPN, ~1 h avant le coup d'envoi)
    # -> active la pondération des absences (availability.py). Zéro invention.
    try:
        from collector import lineup_ingest
        lineup_ingest.ingest_all_upcoming()
    except Exception as e:
        print(f"   [warn] ingestion compos à venir échouée : {e}")
    # head-to-head (confrontations directes) des matchs à venir
    try:
        from collector import h2h_ingest
        h2h_ingest.ingest_all_upcoming()
    except Exception as e:
        print(f"   [warn] ingestion H2H échouée : {e}")

    print("⚙️  5/5 — calibration ρ/γ + régénération des pronostics + intégration page...")
    pipeline.calibrate_dc()            # calibre Dixon-Coles sur les vrais scores
    pipeline.predict()
    player_ingest.export_for_web()
    embed.main()                       # embarque les données dans index.html + scouting.html

    print("\n✅ App réactualisée. Lance :  python3 -m http.server 8077")


if __name__ == "__main__":
    main()
