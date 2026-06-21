"""
Suivi EN DIRECT via l'API ESPN (gratuite, sans clé).

ESPN fournit en temps réel : le score live, la minute de jeu (displayClock),
la période (1ère/2ème MT), et le statut (en cours / terminé). Ce module :

  1) interroge le scoreboard ESPN du jour,
  2) pour chaque match EN COURS -> écrit le score + la minute live dans la base,
  3) pour chaque match qui vient de se TERMINER -> le marque FINISHED + ingère
     les stats complètes (espn_ingest) automatiquement.

RÈGLE N°1 — ZÉRO INVENTION : on n'écrit que ce qu'ESPN renvoie réellement.

Usage :
    python3 -m collector.espn_live            # un cycle (met à jour la base)
    python3 -m collector.espn_live --loop 30  # boucle toutes les 30 s (Ctrl+C pour arrêter)
"""
from __future__ import annotations
import sys, time, datetime, argparse
from collector.db import database as db
from collector.sources import espn_stats as espn

# états ESPN
IN_PROGRESS = {"STATUS_FIRST_HALF", "STATUS_SECOND_HALF", "STATUS_HALFTIME",
               "STATUS_IN_PROGRESS", "STATUS_END_PERIOD", "STATUS_EXTRA_TIME",
               "STATUS_SHOOTOUT", "STATUS_OVERTIME"}
FINISHED = {"STATUS_FULL_TIME", "STATUS_FINAL", "STATUS_FT"}


_STOP = {"dr", "of", "the", "and", "&", "republic", "rep", "ir", "pr"}


def _toks(name):
    """Ensemble de mots significatifs d'un nom (gère 'Congo DR' == 'DR Congo')."""
    return {w for w in espn._norm(name).replace("&", " ").split() if w and w not in _STOP}


def _teams_match(a1, a2, b1, b2):
    """Vrai si les deux paires d'équipes désignent le même match (ordre tolérant)."""
    ta1, ta2, tb1, tb2 = _toks(a1), _toks(a2), _toks(b1), _toks(b2)
    def ov(x, y):
        return bool(x & y)
    return (ov(ta1, tb1) and ov(ta2, tb2)) or (ov(ta1, tb2) and ov(ta2, tb1))


def _find_db_match(conn, home_norm, away_norm):
    """Retrouve le match en base (tolérant aux alias/ordre ESPN, ex. 'Congo DR')."""
    rows = conn.execute("SELECT id, home, away, status FROM matches").fetchall()
    for r in rows:
        if _teams_match(home_norm, away_norm, r["home"], r["away"]):
            return r
    return None


def poll_once(verbose=True):
    """Un cycle : lit ESPN aujourd'hui (+/- 1 jour pour les fuseaux) et met à jour la base."""
    conn = db.init_db()
    today = datetime.date.today()
    seen = {}
    for off in (0, -1, 1):
        for ev in espn.scoreboard(today + datetime.timedelta(days=off)):
            seen[ev["id"]] = ev

    live_n = fin_n = 0
    just_finished = []
    for ev in seen.values():
        state = ev["state"]
        row = _find_db_match(conn, ev["home"], ev["away"])
        if not row:
            continue
        # match déjà figé FINISHED en base -> on ne touche pas (le résultat est intégré)
        if row["status"] == "FINISHED":
            continue

        if state in IN_PROGRESS:
            conn.execute(
                "UPDATE matches SET status='LIVE', home_goals=?, away_goals=?, live_clock=? WHERE id=?",
                (ev["home_goals"], ev["away_goals"], ev.get("clock"), row["id"]))
            live_n += 1
            # Ingest commentary and live events (stats) periodically
            try:
                from collector import espn_ingest
                espn_ingest.ingest_match(row["home"], row["away"], force=True)
            except Exception as e:
                pass
                
            if verbose:
                print(f"  🔴 {row['home']} {ev['home_goals']}-{ev['away_goals']} {row['away']}  ({ev.get('clock') or '?'})")
        elif state in FINISHED or ev.get("completed"):
            conn.execute(
                "UPDATE matches SET status='FINISHED', home_goals=?, away_goals=?, "
                "live_clock=NULL, processed=0 WHERE id=?",
                (ev["home_goals"], ev["away_goals"], row["id"]))
            fin_n += 1
            just_finished.append((row["home"], row["away"], ev["home_goals"], ev["away_goals"]))
            if verbose:
                print(f"  🏁 {row['home']} {ev['home_goals']}-{ev['away_goals']} {row['away']}  (terminé)")
    conn.commit()
    conn.close()

    # ingestion complète des matchs fraîchement terminés (stats + compos + arbitre)
    for home, away, hg, ag in just_finished:
        try:
            from collector import espn_ingest
            espn_ingest.ingest_match(home, away)
        except Exception as e:
            print(f"     [warn] ingestion {home}-{away} : {e}")

    if verbose:
        print(f"→ {live_n} en cours, {fin_n} terminé(s) ce cycle.")
    return {"live": live_n, "finished": fin_n, "just_finished": just_finished}


def main():
    ap = argparse.ArgumentParser(description="Suivi live ESPN (score + minute temps réel)")
    ap.add_argument("--loop", type=int, default=0,
                    help="boucle toutes les N secondes (0 = un seul cycle)")
    args = ap.parse_args()
    if args.loop <= 0:
        poll_once()
        return
    print(f"🔴 Suivi live ESPN — cycle toutes les {args.loop}s (Ctrl+C pour arrêter)\n")
    try:
        while True:
            r = poll_once()
            # si un match vient de finir, on régénère les pronos + page tout de suite
            if r["finished"]:
                try:
                    from collector import pipeline, embed
                    pipeline.update(); pipeline.calibrate_dc(); pipeline.predict(); embed.main()
                    print("   ✅ pronos + page régénérés (match terminé).")
                except Exception as e:
                    print(f"   [warn] régénération : {e}")
            time.sleep(args.loop)
    except KeyboardInterrupt:
        print("\n👋 Arrêt du suivi live.")


if __name__ == "__main__":
    main()
