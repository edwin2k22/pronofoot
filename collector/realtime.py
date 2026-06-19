"""
MACHINE TEMPS RÉEL — l'app se met à jour seule et RECALCULE l'issue à chaque
nouvelle information (compos officielles, cotes, score live, fin de match).

Phases automatiques (pilotées par schedule_clock.live_window) :

  IDLE      -> rien d'imminent : dort jusqu'à ~30 min avant le prochain coup d'envoi.
  PREMATCH  -> T-30 min : récupère COMPOS OFFICIELLES ESPN + COTES à jour,
               applique les absences, RECALCULE l'issue de chaque match concerné.
  SOON      -> T-10 min : re-vérifie compos/cotes (souvent confirmées tard).
  LIVE      -> match en cours : score + minute ESPN, recalcul (live betting), fin auto.

À CHAQUE cycle, on compare l'AVANT/APRÈS et on journalise les VRAIS changements
(ex. "Sénégal 12% -> 14% : Mané titulaire") dans data/live_feed.json, que l'app
affiche en direct. RÈGLE N°1 : aucune donnée inventée, on ne réagit qu'aux vraies
infos ESPN/cotes.

Lancement (dans le sandbox / serveur qui a accès au réseau) :
    python3 -m collector.realtime              # boucle intelligente continue
    python3 -m collector.realtime --once       # un seul cycle (test/demo)
    python3 -m collector.realtime --status      # diagnostic instantané
"""
from __future__ import annotations
import sys, os, time, json, argparse, datetime

from collector import schedule_clock as clock
from collector import espn_live, lineup_ingest, odds_ingest, pipeline, embed
from collector.db import database as db

DATA = os.path.join(os.path.dirname(__file__), "data")
PRED = os.path.join(DATA, "predictions.json")
FEED = os.path.join(DATA, "live_feed.json")
MAX_FEED = 60                     # nb max d'entrées conservées dans le journal


# ---------- snapshot des probas pour détecter les changements ----------
def _snapshot():
    try:
        with open(PRED, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return {}
    snap = {}
    for m in d:
        p = m.get("prediction") or {}
        snap[(m["home"], m["away"])] = {
            "p1": p.get("p1"), "pX": p.get("pX"), "p2": p.get("p2"),
            "status": m.get("status"), "liveScore": m.get("liveScore"),
            "absent": [x["name"] for x in (p.get("availability", {}).get("away", {}).get("missing", [])
                                           + p.get("availability", {}).get("home", {}).get("missing", []))],
        }
    return snap


def _load_feed():
    try:
        with open(FEED, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _save_feed(feed):
    with open(FEED, "w", encoding="utf-8") as f:
        json.dump(feed[:MAX_FEED], f, ensure_ascii=False, indent=2)


def _pct(x):
    return f"{round((x or 0)*100)}%"


def _diff_and_log(before, after, feed, ts):
    """Compare deux snapshots et ajoute les changements significatifs au journal."""
    added = 0
    for key, aft in after.items():
        bef = before.get(key)
        home, away = key
        match = f"{home}–{away}"
        if not bef:
            continue
        # changement de statut (coup d'envoi, fin…)
        if bef["status"] != aft["status"]:
            lbl = {"LIVE": "🟢 coup d'envoi", "FINISHED": "🏁 match terminé"}.get(aft["status"], aft["status"])
            feed.insert(0, {"t": ts, "match": match, "type": "status",
                            "text": f"{match} : {lbl}"})
            added += 1
        # score live qui bouge
        if aft["status"] == "LIVE" and bef.get("liveScore") != aft.get("liveScore") and aft.get("liveScore"):
            feed.insert(0, {"t": ts, "match": match, "type": "score",
                            "text": f"⚽ {match} : score {aft['liveScore']}"})
            added += 1
        # nouvelles absences détectées (compo officielle)
        new_abs = set(aft.get("absent", [])) - set(bef.get("absent", []))
        if new_abs:
            feed.insert(0, {"t": ts, "match": match, "type": "lineup",
                            "text": f"🩹 {match} : absent(s) → {', '.join(sorted(new_abs))}"})
            added += 1
        # variation notable des probas (≥ 3 points)
        for k, lbl in [("p1", home), ("pX", "nul"), ("p2", away)]:
            b, a = bef.get(k), aft.get(k)
            if b is not None and a is not None and abs(a-b) >= 0.03:
                arrow = "↗" if a > b else "↘"
                feed.insert(0, {"t": ts, "match": match, "type": "proba",
                                "text": f"📊 {match} : {lbl} {_pct(b)}{arrow}{_pct(a)}"})
                added += 1
    return added


# ---------- cycles par phase ----------
def cycle_prematch(matches, label="PREMATCH"):
    """Compos officielles + cotes + recalcul de l'issue, avec journal des changements."""
    before = _snapshot()
    ts = datetime.datetime.now().strftime("%H:%M")
    changed = []
    for m in matches:
        h, a = m["home"], m["away"]
        ok, msg = lineup_ingest.ingest_lineup(h, a)
        if ok:
            changed.append(f"compo {h}-{a}")
    # cotes à jour (toutes les rencontres à venir)
    try:
        odds_ingest.main()
    except Exception as e:
        print(f"   [warn] cotes : {e}")
    # recalcul complet de l'issue (intègre absences + cotes + apprentissage)
    pipeline.predict()
    embed.main()
    after = _snapshot()
    feed = _load_feed()
    n = _diff_and_log(before, after, feed, ts)
    if n:
        _save_feed(feed)
    print(f"[{ts}] {label} : {len(matches)} match(s) surveillé(s), {n} changement(s) journalisé(s).")
    return n


def cycle_live():
    """Score + minute ESPN, recalcul (live betting), fin de match automatique."""
    before = _snapshot()
    ts = datetime.datetime.now().strftime("%H:%M")
    res = espn_live.poll_once(verbose=False)
    pipeline.update()
    pipeline.predict()
    embed.main()
    after = _snapshot()
    feed = _load_feed()
    n = _diff_and_log(before, after, feed, ts)
    if n:
        _save_feed(feed)
    print(f"[{ts}] LIVE : {res['live']} en cours, {res['finished']} terminé(s), {n} changement(s).")
    return n


def one_cycle(verbose=True):
    """Exécute le cycle correspondant à la phase courante (utile pour --once)."""
    w = clock.live_window(pre_min=10, prematch_min=30)
    st = w["state"]
    if verbose:
        print(f"🕐 État : {st}")
    if st == "LIVE":
        return cycle_live()
    if st in ("PREMATCH", "SOON"):
        return cycle_prematch(w["prematch_matches"] or ([w["next_match"]] if w["next_match"] else []),
                              label=st)
    print("   (rien d'imminent — IDLE)")
    return 0


def run(live_poll=30, prematch_poll=120):
    print("🤖 MACHINE TEMPS RÉEL démarrée — l'app se met à jour et recalcule seule.")
    print(f"   LIVE : toutes les {live_poll}s · PRÉ-MATCH (T-30) : toutes les {prematch_poll}s")
    print("   (Ctrl+C pour arrêter)\n")
    while True:
        w = clock.live_window(pre_min=10, prematch_min=30)
        st = w["state"]
        ts = w["now"].strftime("%H:%M:%S")
        try:
            if st == "LIVE":
                cycle_live(); sleep = live_poll
            elif st in ("PREMATCH", "SOON"):
                cycle_prematch(w["prematch_matches"], label=st)
                sleep = prematch_poll if st == "PREMATCH" else 60
            else:
                secs = w["seconds_to_next"]
                if secs is None:
                    print(f"[{ts}] 💤 plus aucun match au calendrier. Arrêt."); break
                # se réveiller ~30 min avant le coup d'envoi
                sleep = max(30, min(secs - 30*60, 1800))
                nm = w["next_match"]
                print(f"[{ts}] 💤 veille — prochain : {nm['home']}-{nm['away']} "
                      f"(réveil dans {sleep/60:.0f} min)")
        except Exception as e:
            print(f"[{ts}] [warn] cycle {st} échoué : {e}")
            sleep = 60
        try:
            time.sleep(sleep)
        except KeyboardInterrupt:
            print("\n👋 Machine temps réel arrêtée."); break


def main():
    ap = argparse.ArgumentParser(description="Machine temps réel CDM 2026")
    ap.add_argument("--once", action="store_true", help="un seul cycle puis stop")
    ap.add_argument("--status", action="store_true", help="diagnostic instantané")
    ap.add_argument("--live-poll", type=int, default=30)
    ap.add_argument("--prematch-poll", type=int, default=120)
    args = ap.parse_args()
    if args.status:
        w = clock.live_window(pre_min=10, prematch_min=30)
        print(f"État : {w['state']} | prochain : "
              f"{(w['next_match'] or {}).get('home','—')}-{(w['next_match'] or {}).get('away','')} "
              f"dans {(w['seconds_to_next'] or 0)/60:.0f} min")
        print(f"Matchs en pré-match (≤30min) : {[m['home']+'-'+m['away'] for m in w['prematch_matches']]}")
        print(f"Matchs en cours : {[m['home']+'-'+m['away'] for m in w['live_matches']]}")
    elif args.once:
        one_cycle()
    else:
        run(args.live_poll, args.prematch_poll)


if __name__ == "__main__":
    main()
