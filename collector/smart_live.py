#!/usr/bin/env python3
"""
Scheduler LIVE intelligent — s'active tout seul quand un match commence.

Au lieu de marteler l'API en continu, il connaît le calendrier et adapte son rythme :

  ┌─ état ──┬─ situation ───────────────────┬─ action ─────────────────────────┐
  │ LIVE    │ ≥1 match en cours             │ poll rapide (ex 30 s) : live + predict │
  │ SOON    │ coup d'envoi dans < 10 min    │ poll moyen (ex 60 s), prêt à activer   │
  │ IDLE    │ rien avant longtemps          │ DORT jusqu'à ~5 min avant le match     │
  └─────────┴───────────────────────────────┴────────────────────────────────────┘

Avantages : respecte l'API gratuite, ne tourne pas pour rien la nuit, mais ne rate
jamais un coup d'envoi (réveil automatique avant chaque match).

Usage :
    python3 -m collector.smart_live                 # mode intelligent (défaut)
    python3 -m collector.smart_live --live-poll 20  # poll toutes les 20s en match
    python3 -m collector.smart_live --status        # diagnostic instantané
"""
from __future__ import annotations
import sys, os, time, argparse
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector import schedule_clock as clock
from collector import live, pipeline, player_ingest

WAKE_BEFORE_MIN = 5         # se réveiller 5 min avant un coup d'envoi
MAX_IDLE_SLEEP = 1800       # ne jamais dormir plus de 30 min d'un coup (re-check calendrier)


def _fmt(dt):
    return dt.strftime("%H:%M UTC") if dt else "—"


last_stats_pull = 0

def do_live_cycle():
    """Un cycle live : score+minute ESPN temps réel, met à jour Elo si match fini, predict."""
    global last_stats_pull
    import datetime
    from collector import realtime
    before = realtime._snapshot()
    try:
        from collector import espn_live
        espn_live.poll_once(verbose=False)   # SOURCE PRINCIPALE : ESPN (score + minute live)
    except Exception as e:
        print(f"   [warn] live ESPN : {e}")
    try:
        live.auto_pull()                     # filet de sécurité (worldcup26.ir)
    except Exception:
        pass
    pipeline.ingest(); pipeline.update()
    pipeline.predict()
    player_ingest.export_for_web()
    after = realtime._snapshot()
    feed = realtime._load_feed()
    ts = datetime.datetime.now().strftime("%H:%M")
    n = realtime._diff_and_log(before, after, feed, ts)
    if n:
        realtime._save_feed(feed)
    
    # Auto-pull detailed stats every 10 min if a finished match is missing them
    if time.time() - last_stats_pull > 600:
        try:
            from collector.db import database as db
            conn = db.init_db()
            missing = conn.execute("SELECT id FROM matches WHERE status='FINISHED' AND home_xg IS NULL AND datetime(utc_date) > datetime('now', '-24 hours')").fetchone()
            if missing:
                print("   [smart_live] Match terminé sans stats détaillées détecté. Lancement de l'import Opta...")
                from collector import espn_ingest, import_stats
                espn_ingest.main()
                import_stats.main()
                pipeline.predict() # Refresh predictions with new stats
        except Exception as e:
            print(f"   [warn] échec import_stats : {e}")
        finally:
            last_stats_pull = time.time()
            
    # Always embed data into index.html so static files stay fresh
    try:
        from collector import embed
        embed.main()
    except Exception:
        pass


def status_once():
    w = clock.live_window(pre_min=10)
    print(f"🕐 {w['now'].strftime('%Y-%m-%d %H:%M UTC')} — état : {w['state']}")
    if w["live_matches"]:
        for m in w["live_matches"]:
            print(f"   🔴 EN COURS : {m['home']} vs {m['away']} (coup d'envoi {_fmt(m['kickoff'])})")
    if w["next_match"]:
        nm = w["next_match"]
        secs = w["seconds_to_next"] or 0
        print(f"   ⏭  prochain : {nm['home']} vs {nm['away']} à {_fmt(nm['kickoff'])} "
              f"(dans {secs/3600:.1f} h)")


def run(live_poll: int, soon_poll: int):
    print("🧠 Scheduler LIVE intelligent démarré.")
    print(f"   poll en match : {live_poll}s · veille : réveil {WAKE_BEFORE_MIN} min avant chaque match")
    print("   (Ctrl+C pour arrêter)\n")

    while True:
        w = clock.live_window(pre_min=10)
        state = w["state"]
        ts = w["now"].strftime("%H:%M:%S")

        if state == "LIVE":
            names = ", ".join(f"{m['home']}-{m['away']}" for m in w["live_matches"])
            print(f"[{ts}] 🔴 LIVE ({names}) — actualisation...")
            try:
                do_live_cycle()
            except Exception as e:
                print(f"   [warn] cycle live échoué : {e}")
            sleep = live_poll

        elif state == "SOON":
            print(f"[{ts}] ⏳ coup d'envoi imminent ({_fmt(w['next_kickoff'])}) — veille active.")
            sleep = soon_poll

        else:  # IDLE
            secs = w["seconds_to_next"]
            if secs is None:
                print(f"[{ts}] 💤 plus aucun match au calendrier. Arrêt.")
                break
            # dormir jusqu'à WAKE_BEFORE_MIN avant le coup d'envoi (borné)
            wake_in = max(30, secs - WAKE_BEFORE_MIN * 60)
            sleep = min(wake_in, MAX_IDLE_SLEEP)
            nm = w["next_match"]
            print(f"[{ts}] 💤 veille — prochain : {nm['home']}-{nm['away']} à "
                  f"{_fmt(w['next_kickoff'])} (réveil dans {sleep/60:.0f} min)")

        try:
            time.sleep(sleep)
        except KeyboardInterrupt:
            print("\n👋 Scheduler arrêté.")
            break


def main():
    ap = argparse.ArgumentParser(description="Scheduler live intelligent CDM 2026")
    ap.add_argument("--live-poll", type=int, default=30, help="secondes entre actualisations EN MATCH (défaut 30)")
    ap.add_argument("--soon-poll", type=int, default=60, help="secondes en phase 'imminent' (défaut 60)")
    ap.add_argument("--status", action="store_true", help="diagnostic instantané puis stop")
    args = ap.parse_args()
    if args.status:
        status_once()
    else:
        run(args.live_poll, args.soon_poll)


if __name__ == "__main__":
    main()
