"""
Ingestion des COTES réelles (1N2 + O/U) depuis ESPN -> collector/data/odds_real.json
+ Ajout de l'intégration Smarkets pour BTTS, Corners et Cartons.

Source : ESPN summary (pickcenter / odds) + API Smarkets.
"""
from __future__ import annotations
import sys, os, json, re, datetime
from collector.sources import espn_stats as espn
from collector.sources import smarkets_odds as smarkets
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


def ingest_match(home, away, date_hint=None, smarkets_dict=None):
    if smarkets_dict is None:
        smarkets_dict = {}
        
    ev = None
    for off in ((0, 1, -1) if date_hint else (None,)):
        d = date_hint + datetime.timedelta(days=off) if (date_hint and off is not None) else None
        ev = espn.find_event(home, away, d)
        if ev:
            break
            
    od = espn.match_odds(ev["id"]) if ev else None
    
    key = f"{home}|{away}"
    sm_odds = smarkets_dict.get(key, {})
    
    if not od and not sm_odds:
        print(f"  [skip] {home} vs {away} : pas de cotes ESPN ni Smarkets")
        return False
        
    if not od:
        # Fallback if only Smarkets has odds
        od = {"provider": "Smarkets", "odd1": 0, "oddX": 0, "odd2": 0}
        
    store = _load()
    prev = store.get(key, {})
    od["opening"] = prev.get("opening") or {"odd1": od.get("odd1"), "oddX": od.get("oddX"), "odd2": od.get("odd2")}
    od["captured"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Merge Smarkets odds
    for k, v in sm_odds.items():
        od[k] = v
        
    store[key] = od
    _save(store)
    print(f"  ✅ {home} {od.get('odd1')} / {od.get('oddX')} / {od.get('odd2')} {away} (O/U {od.get('ou_line')}) [+ {len(sm_odds)} marchés Smarkets]")
    return True


def main():
    if len(sys.argv) >= 3:
        ingest_match(sys.argv[1], sys.argv[2])
        return
    conn = db.init_db()
    rows = conn.execute("SELECT home, away, utc_date FROM matches "
                        "WHERE status IN ('SCHEDULED','LIVE','HT') ORDER BY utc_date").fetchall()
    conn.close()
    
    print(f"⚙️  Ingestion cotes ESPN + Smarkets ({len(rows)} matchs à venir/en cours)…")
    # Fetch all Smarkets odds in batch
    smarkets_dict = smarkets.get_match_odds(rows)
    
    ok = 0
    for r in rows:
        if ingest_match(r["home"], r["away"], _date(r["utc_date"]), smarkets_dict):
            ok += 1
    print(f"\n✅ {ok}/{len(rows)} matchs avec cotes réelles.")
    print("   Relance :  python3 -m collector.pipeline predict && python3 -m collector.embed")


if __name__ == "__main__":
    main()
