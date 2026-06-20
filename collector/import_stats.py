#!/usr/bin/env python3
"""
Importe les VRAIES stats des matchs terminés (collectées sur le web) dans la base.

Source : collector/data/match_stats_real.json (xG, tirs, corners, cartons par match).
Ces stats viennent des box scores publics (Opta, Sofascore, 365scores, FOX...).

Remplit les colonnes home_xg/away_xg, home_shots..., home_corners..., home_cards...
des matchs déjà FINISHED, pour que l'analyse post-match ne soit plus en N/D.

Usage :
    python3 -m collector.import_stats
"""
from __future__ import annotations
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector.db import database as db

DATA = os.path.join(os.path.dirname(__file__), "data", "match_stats_real.json")
EVENTS = os.path.join(os.path.dirname(__file__), "data", "match_events_real.json")
LINEUPS = os.path.join(os.path.dirname(__file__), "data", "match_lineups_real.json")


def main():
    if not os.path.exists(DATA):
        print(f"❌ {DATA} introuvable."); return
    with open(DATA, encoding="utf-8") as f:
        stats = json.load(f)
    events = {}
    if os.path.exists(EVENTS):
        with open(EVENTS, encoding="utf-8") as f:
            events = json.load(f)
    lineups = {}
    if os.path.exists(LINEUPS):
        with open(LINEUPS, encoding="utf-8") as f:
            lineups = json.load(f)

    conn = db.init_db()
    n = 0
    for key, s in stats.items():
        if key.startswith("_"):
            continue
        home, away = key.split("|", 1)
        row = conn.execute(
            "SELECT id, status, events_json FROM matches WHERE home=? AND away=?", (home, away)).fetchone()
        if not row:
            print(f"  [skip] match introuvable : {home} vs {away}")
            continue
        ev = dict(events.get(key) or {})
        if lineups.get(key):
            ev["lineups"] = lineups[key]      # compos intégrées au bloc events
        else:
            # PRÉSERVE les compos déjà en base (ex. ingérées par espn_ingest) :
            # ne pas les écraser parce que le fichier match_lineups_real.json ne les a pas.
            try:
                prev = json.loads(row["events_json"]) if row["events_json"] else {}
                if isinstance(prev, dict) and prev.get("lineups"):
                    ev["lineups"] = prev["lineups"]
            except (TypeError, ValueError):
                pass
        ev_json = json.dumps(ev, ensure_ascii=False) if ev else None
        # stats d'équipe ÉTENDUES (possession, passes, tacles…) -> blob JSON
        EXT = ["possession", "passes", "passes_ok", "pass_pct", "crosses", "crosses_ok",
               "long_balls", "tackles", "tackles_won", "interceptions", "clearances",
               "blocked_shots", "fouls", "offsides", "saves"]
        team_ext = {}
        for side in ("home", "away"):
            for f in EXT:
                v = s.get(f"{side}_{f}")
                if v is not None:
                    team_ext[f"{side}_{f}"] = v
        ts_json = json.dumps(team_ext, ensure_ascii=False) if team_ext else None
        ht = ev.get("halftime")
        home_ht_goals = None
        away_ht_goals = None
        if ht and "-" in ht:
            try:
                parts = ht.split("-")
                home_ht_goals = int(parts[0])
                away_ht_goals = int(parts[1])
            except (ValueError, IndexError):
                pass

        conn.execute("""UPDATE matches SET
            home_xg=?, away_xg=?, home_shots=?, away_shots=?,
            home_shots_on=?, away_shots_on=?,
            home_corners=?, away_corners=?, home_cards=?, away_cards=?,
            home_ht_goals=?, away_ht_goals=?,
            events_json=?, team_stats_json=?
            WHERE id=?""",
            (s.get("home_xg"), s.get("away_xg"), s.get("home_shots"), s.get("away_shots"),
             s.get("home_shots_on"), s.get("away_shots_on"),
             s.get("home_corners"), s.get("away_corners"), s.get("home_cards"), s.get("away_cards"),
             home_ht_goals, away_ht_goals,
             ev_json, ts_json, row["id"]))
        n += 1
        gtxt = ""
        if ev.get("goals"):
            gtxt = " | buts: " + ", ".join(f"{g['player']} {g['minute']}'" for g in ev["goals"])
        ltxt = " + compos" if ev.get("lineups") else ""
        xgtxt = f" {s['home_xg']}xG - {s['away_xg']}xG" if s.get("home_xg") is not None else ""
        print(f"  ✅ {home}{xgtxt} {away}{gtxt}{ltxt}")
    conn.commit(); conn.close()
    print(f"\n✅ {n} matchs enrichis (stats + buteurs + compos).")


if __name__ == "__main__":
    main()
