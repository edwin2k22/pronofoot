"""
Ingestion des COTES réelles (1N2 + O/U) depuis ESPN -> collector/data/odds_real.json

Les cotes débloquent : Kelly fractionné, détection de value, line movement.
Source : ESPN summary (pickcenter / odds), GRATUIT sans clé. Cotes converties en décimal.

Usage :
    python3 -m collector.odds_ingest                  # tous les matchs SCHEDULED/LIVE
    python3 -m collector.odds_ingest "France" "Senegal"
"""
from __future__ import annotations
import sys, os, json, re, datetime
from collector.sources import espn_stats as espn
from collector.db import database as db

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ODDS_FILE = os.path.join(DATA, "odds_real.json")


def _load():
    try:
        with open(ODDS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(d):
    with open(ODDS_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def _date(s):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s or "")
    return datetime.date(int(m[1]), int(m[2]), int(m[3])) if m else None


def ingest_match(home, away, date_hint=None):
    ev = None
    for off in ((0, 1, -1) if date_hint else (None,)):
        d = date_hint + datetime.timedelta(days=off) if (date_hint and off is not None) else None
        ev = espn.find_event(home, away, d)
        if ev:
            break
    if not ev:
        print(f"  [skip] {home} vs {away} : introuvable sur ESPN")
        return False
    od = espn.match_odds(ev["id"])
    if not od or not od.get("odd1"):
        print(f"  [skip] {home} vs {away} : pas de cotes ESPN")
        return False
    store = _load()
    # garde la 1re cote vue comme "ouverture" pour le line movement
    key = f"{home}|{away}"
    prev = store.get(key, {})
    od["opening"] = prev.get("opening") or {"odd1": od["odd1"], "oddX": od["oddX"], "odd2": od["odd2"]}
    od["captured"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    store[key] = od
    _save(store)
    print(f"  ✅ {home} {od['odd1']} / {od['oddX']} / {od['odd2']} {away}  (O/U {od['ou_line']}) [{od['provider']}]")
    return True


def main():
    if len(sys.argv) >= 3:
        ingest_match(sys.argv[1], sys.argv[2])
        return
    conn = db.init_db()
    rows = conn.execute("SELECT home, away, utc_date FROM matches "
                        "WHERE status IN ('SCHEDULED','LIVE','HT') ORDER BY utc_date").fetchall()
    conn.close()
    print(f"⚙️  Ingestion cotes ESPN ({len(rows)} matchs à venir/en cours)…")
    ok = 0
    for r in rows:
        if ingest_match(r["home"], r["away"], _date(r["utc_date"])):
            ok += 1
    print(f"\n✅ {ok}/{len(rows)} matchs avec cotes réelles.")
    print("   Relance :  python3 -m collector.pipeline predict && python3 -m collector.embed")


if __name__ == "__main__":
    main()
