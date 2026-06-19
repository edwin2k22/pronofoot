"""
Ingestion HEAD-TO-HEAD (confrontations directes) via ESPN pour les matchs à venir.

Construit collector/data/h2h.json = {"Home|Away": {refTeam, games[], summary}}.
Lu par embed.py et affiché dans le panneau d'analyse. 100% données réelles ESPN.

Usage :
    python3 -m collector.h2h_ingest            # tous les matchs SCHEDULED proches
    python3 -m collector.h2h_ingest "France" "Iraq"
"""
from __future__ import annotations
import os, json, sys
from collector.db import database as db
from collector.sources import espn_stats as espn

DATA = os.path.join(os.path.dirname(__file__), "data")
H2H_FILE = os.path.join(DATA, "h2h.json")


def _load():
    try:
        with open(H2H_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def ingest(home, away):
    ev = espn.find_event(home, away)
    if not ev:
        return False, "événement ESPN introuvable"
    h2h = espn.match_h2h(ev["id"])
    if not h2h:
        return False, "pas d'historique H2H"
    data = _load()
    # oriente le résumé du point de vue de l'équipe DOMICILE de notre base
    ref = (h2h.get("refTeam") or "").lower()
    s = h2h["summary"]
    if ref and away.lower().split()[-1] in ref:   # refTeam = away -> on inverse
        s = {"win": s["loss"], "draw": s["draw"], "loss": s["win"], "total": s["total"]}
        h2h["games"] = [{**g, "score": "-".join(g["score"].split("-")[::-1])} for g in h2h["games"]]
    h2h["summary"] = s
    h2h["home"] = home; h2h["away"] = away
    data[f"{home}|{away}"] = h2h
    with open(H2H_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return True, f"{s['total']} confrontations"


def ingest_all_upcoming(limit=24):
    conn = db.init_db()
    rows = conn.execute(
        "SELECT home, away FROM matches WHERE status='SCHEDULED' ORDER BY utc_date LIMIT ?",
        (limit,)).fetchall()
    conn.close()
    done = 0
    for r in rows:
        ok, msg = ingest(r["home"], r["away"])
        if ok:
            done += 1
    print(f"✅ H2H : {done}/{len(rows)} matchs avec historique ingéré")
    return done


def main():
    if len(sys.argv) >= 3:
        ok, msg = ingest(sys.argv[1], sys.argv[2])
        print(("✅ " if ok else "· ") + msg)
    else:
        ingest_all_upcoming()


if __name__ == "__main__":
    main()
