"""
Ingestion AUTOMATIQUE des arbitres désignés pour les matchs À VENIR.

ESPN publie l'arbitre dans gameInfo.officials, souvent ~24-48 h avant le match
(parfois plus tôt). On le récupère et on :
  1) l'injecte dans match_stats_real.json (pour le fallback _real_referee())
  2) l'ajoute dynamiquement au dictionnaire referees_2026.ASSIGNMENTS
     (pour que le pipeline le voie immédiatement au predict())

RÈGLE N°1 — ZÉRO INVENTION : on n'écrit l'arbitre QUE s'il est réellement publié
par ESPN. Sinon on ne touche à rien.

Usage :
  python3 -m collector.referee_ingest                # tous les matchs SCHEDULED
  python3 -m collector.referee_ingest "France" "Iraq"  # un match précis
"""
from __future__ import annotations
import json, os, sys

from collector.db import database as db
from collector.sources import espn_stats as espn
from collector.sources import referees_2026 as refs
from collector.sources import referee_form as refform

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
STATS_FILE = os.path.join(DATA, "match_stats_real.json")


def _load_stats():
    try:
        with open(STATS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_stats(data):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=1)


def ingest_referee(home: str, away: str) -> tuple[bool, str]:
    """Tente de récupérer l'arbitre d'un match depuis ESPN.

    Returns (True, msg) si un arbitre a été trouvé et injecté, (False, msg) sinon.
    """
    # déjà connu dans le dictionnaire hardcodé ?
    existing = refs.get_referee(home, away)
    if existing and existing.get("name"):
        return False, f"déjà connu : {existing['name']} (dictionnaire)"

    # cherche sur ESPN
    ev = espn.find_event(home, away)
    if not ev:
        return False, "événement ESPN introuvable"

    summ = espn.match_summary(ev["id"])
    if not summ:
        return False, "résumé ESPN indisponible"

    ref_name = summ.get("referee")
    if not ref_name:
        return False, "arbitre pas encore publié sur ESPN"

    # ---- injection 1 : match_stats_real.json (fallback _real_referee) ----
    stats = _load_stats()
    key = f"{home}|{away}"
    cur = stats.get(key, {})
    cur["referee"] = ref_name
    stats[key] = cur
    _save_stats(stats)

    # ---- injection 2 : dictionnaire en mémoire (pour le predict() courant) ----
    refs.ASSIGNMENTS[(home, away)] = (ref_name, None)

    # ---- injection 3 : sévérité connue ? ----
    sev = refs.SEVERITY.get(ref_name)
    sev_str = f", sévérité {sev}" if sev else ""

    return True, f"✅ {ref_name}{sev_str}"


def ingest_all_upcoming():
    """Parcourt les matchs SCHEDULED et tente d'ingérer leur arbitre."""
    conn = db.init_db()
    rows = conn.execute(
        "SELECT home, away FROM matches WHERE status='SCHEDULED' ORDER BY utc_date LIMIT 40"
    ).fetchall()
    conn.close()

    done = 0
    for r in rows:
        ok, msg = ingest_referee(r["home"], r["away"])
        flag = "✅" if ok else "·"
        print(f"  {flag} {r['home']} vs {r['away']} — {msg}")
        if ok:
            done += 1
    print(f"\n{done} arbitre(s) ingéré(s) automatiquement depuis ESPN.")
    return done


def main():
    if len(sys.argv) >= 3:
        ok, msg = ingest_referee(sys.argv[1], sys.argv[2])
        print(("✅ " if ok else "· ") + msg)
    else:
        ingest_all_upcoming()


if __name__ == "__main__":
    main()
