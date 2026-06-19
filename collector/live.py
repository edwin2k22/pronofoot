#!/usr/bin/env python3
"""
Mode LIVE — ingestion des matchs en cours / terminés au fil de l'eau.

Réactive le suivi en direct (mis de côté précédemment). Deux principes de sûreté :
  • Un match LIVE (non terminé) est stocké et affiché, mais N'IMPACTE PAS les
    ratings Elo tant qu'il n'est pas FINISHED (on ne met pas à jour la force d'une
    équipe sur un score provisoire — anti-overreaction).
  • Quand le match passe FINISHED, le pipeline.update() l'intègre normalement.

Sources de scores 2026 :
  - openfootball (MAJ quotidienne) : scores finaux fiables
  - saisie manuelle / web (--set) : pour le live avant que openfootball publie

Usage :
    python3 -m collector.live --status                       # voir l'état live
    python3 -m collector.live --set "Canada" "Bosnia & Herzegovina" 0 1 --state LIVE \
            --minute 45 --poss 66 34 --xg 0.59 0.77 --shots 8 4 --corners 9 1 --cards 1 2
    python3 -m collector.live --sync                         # tire les scores finaux d'openfootball
"""
from __future__ import annotations
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector.db import database as db
from collector.sources import openfootball_wc
from collector.sources import livescore_wc26


def _find_match(conn, home, away):
    return conn.execute(
        "SELECT * FROM matches WHERE home=? AND away=?", (home, away)).fetchone()


def set_live(home, away, gh, ga, state="LIVE", **stats):
    """Met à jour un match avec un score (provisoire ou final) + stats optionnelles."""
    conn = db.init_db()
    mt = _find_match(conn, home, away)
    if not mt:
        print(f"  [warn] match introuvable : {home} vs {away}")
        conn.close(); return
    cols = {"home_goals": gh, "away_goals": ga, "status": state}
    # stats collectives optionnelles
    for k_db, k in [("home_xg", "xg_home"), ("away_xg", "xg_away"),
                    ("home_shots", "shots_home"), ("away_shots", "shots_away"),
                    ("home_corners", "corners_home"), ("away_corners", "corners_away"),
                    ("home_cards", "cards_home"), ("away_cards", "cards_away")]:
        if stats.get(k) is not None:
            cols[k_db] = stats[k]
    sets = ", ".join(f"{c}=?" for c in cols)
    conn.execute(f"UPDATE matches SET {sets} WHERE id=?", (*cols.values(), mt["id"]))
    # un match repassé en LIVE ne doit pas rester "processed"
    if state != "FINISHED":
        conn.execute("UPDATE matches SET processed=0 WHERE id=?", (mt["id"],))
    conn.commit(); conn.close()
    tag = "🔴 LIVE" if state == "LIVE" else ("✅ FINI" if state == "FINISHED" else state)
    print(f"  {tag}  {home} {gh}-{ga} {away}" + (f" ({stats.get('minute')}')" if stats.get("minute") else ""))


def sync_openfootball():
    """Tire les scores FINAUX publiés par openfootball (fiable, MAJ quotidienne)."""
    conn = db.init_db()
    sched = openfootball_wc.load_schedule(ttl=0)
    n = 0
    for m in sched.get("matches", []):
        ft = m.get("score", {}).get("ft")
        if not ft:
            continue
        t1, t2 = m.get("team1"), m.get("team2")
        mt = _find_match(conn, t1, t2)
        if mt and mt["status"] != "FINISHED":
            db.record_result(conn, mt["id"], home_goals=ft[0], away_goals=ft[1])
            n += 1
    conn.commit(); conn.close()
    print(f"  ↻ openfootball sync : {n} match(s) passé(s) FINISHED.")


def auto_pull():
    """
    Tire automatiquement les scores live/finaux depuis worldcup26.ir (temps réel).
    Met à jour la base : LIVE n'impacte pas les Elo, FINISHED sera intégré par update().
    """
    conn = db.init_db()
    games = livescore_wc26.fetch_live(ttl=20)
    n_live = n_fin = 0
    for g in games:
        if g["home_score"] is None:
            continue  # pas commencé
        mt = _find_match(conn, g["home"], g["away"])
        if not mt:
            continue
        if mt["status"] == "FINISHED":
            continue  # déjà finalisé
        if g["state"] == "FINISHED":
            db.record_result(conn, mt["id"],
                             home_goals=g["home_score"], away_goals=g["away_score"])
            n_fin += 1
        elif g["state"] == "LIVE":
            conn.execute("""UPDATE matches SET home_goals=?, away_goals=?,
                            status='LIVE', processed=0 WHERE id=?""",
                         (g["home_score"], g["away_score"], mt["id"]))
            n_live += 1
    conn.commit(); conn.close()
    print(f"  📡 worldcup26.ir : {n_live} LIVE mis à jour, {n_fin} passé(s) FINISHED.")
    return n_live, n_fin


def status():
    conn = db.init_db()
    live = conn.execute("SELECT * FROM matches WHERE status='LIVE' ORDER BY utc_date").fetchall()
    fin = conn.execute("SELECT COUNT(*) c FROM matches WHERE status='FINISHED'").fetchone()["c"]
    print(f"État : {len(live)} match(s) LIVE, {fin} terminé(s).")
    for m in live:
        print(f"  🔴 {m['home']} {m['home_goals']}-{m['away_goals']} {m['away']} [{m['stage']}]")
    conn.close()


def main():
    ap = argparse.ArgumentParser(description="Mode live CDM 2026")
    ap.add_argument("--set", nargs=4, metavar=("HOME", "AWAY", "GH", "GA"),
                    help="définir un score")
    ap.add_argument("--state", default="LIVE", choices=["LIVE", "FINISHED", "HT"])
    ap.add_argument("--minute", type=int)
    ap.add_argument("--poss", nargs=2, type=float, metavar=("H", "A"))
    ap.add_argument("--xg", nargs=2, type=float, metavar=("H", "A"))
    ap.add_argument("--shots", nargs=2, type=int, metavar=("H", "A"))
    ap.add_argument("--corners", nargs=2, type=int, metavar=("H", "A"))
    ap.add_argument("--cards", nargs=2, type=int, metavar=("H", "A"))
    ap.add_argument("--sync", action="store_true", help="sync scores finaux openfootball")
    ap.add_argument("--auto", action="store_true", help="tirer les live scores worldcup26.ir (temps réel)")
    ap.add_argument("--status", action="store_true", help="afficher l'état live")
    args = ap.parse_args()

    if args.auto:
        auto_pull()
    if args.sync:
        sync_openfootball()
    if args.set:
        home, away, gh, ga = args.set
        kw = {"minute": args.minute}
        if args.xg: kw["xg_home"], kw["xg_away"] = args.xg
        if args.shots: kw["shots_home"], kw["shots_away"] = args.shots
        if args.corners: kw["corners_home"], kw["corners_away"] = args.corners
        if args.cards: kw["cards_home"], kw["cards_away"] = args.cards
        set_live(home, away, int(gh), int(ga), state=args.state, **kw)
    if args.status or not (args.set or args.sync or args.auto):
        status()


if __name__ == "__main__":
    main()
