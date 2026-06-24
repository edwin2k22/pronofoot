"""
Ingestion des stats RÉELLES par joueur depuis ESPN -> player_stats_real.json
+ stats équipe (tirs/cadrés/corners/cartons) -> match_stats_real.json.

Usage :
    python3 -m collector.espn_ingest                 # tous les matchs FINISHED de la base
    python3 -m collector.espn_ingest "Ivory Coast" "Ecuador"   # un match précis

Après : relancer  python3 -m collector.refresh  pour réembarquer.
"""
from __future__ import annotations
import sys, os, json, re, datetime
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')
from collector.sources import espn_stats as espn
from collector.sources import referee_form as refform
from collector.db import database as db

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PLAYER_FILE = os.path.join(DATA, "player_stats_real.json")
STATS_FILE = os.path.join(DATA, "match_stats_real.json")
LINEUP_FILE = os.path.join(DATA, "match_lineups_real.json")
EVENT_FILE = os.path.join(DATA, "match_events_real.json")


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(path, data):
    import time
    for _ in range(5):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=True, indent=1)
            return
        except OSError as e:
            time.sleep(0.5)
            last_err = e
    print(f"Failed to save {path}: {last_err}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=1)


def _match_date(date_str):
    """Extrait la date calendaire d'un utc_date type '2026-06-14 19:00 UTC-4'."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", date_str or "")
    if not m:
        return None
    return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def ingest_match(home, away, date_hint=None, force=False):
    key = f"{home}|{away}"

    # cherche la date du match (±1 jour pour gérer les fuseaux/nuit) si fournie
    ev = None
    if date_hint:
        for off in (0, 1, -1):
            ev = espn.find_event(home, away, date_hint + datetime.timedelta(days=off))
            if ev:
                break
    if not ev:
        ev = espn.find_event(home, away)
    if not ev:
        print(f"  [skip] {home} vs {away} : introuvable sur ESPN")
        stats_cache = _load(STATS_FILE)
        stats_cache[f"{home}|{away}"] = {"source_espn": "not_found", "home_shots": None}
        _save(STATS_FILE, stats_cache)
        return False
    summ = espn.match_summary(ev["id"])
    if not summ:
        print(f"  [skip] {home} vs {away} : résumé ESPN indisponible")
        return False

    # 1) stats joueur (fusion cumulative : on additionne les stats numériques)
    players = _load(PLAYER_FILE)
    n_players = 0
    for team, pls in summ["players"].items():
        players.setdefault(team, {})
        for name, rec in pls.items():
            curr = players[team].get(name, {})
            merged = {}
            # Strings: on conserve le plus récent
            for k in ["poste", "statut"]:
                merged[k] = rec.get(k) or curr.get(k)
                
            # Numériques: addition
            numeric_keys = ["minutes", "buts", "passes_dec", "tirs", "tirs_cadres", 
                            "fautes_commises", "fautes_subies", "hors_jeu", "saves", 
                            "shots_faced", "goals_conceded", "but_csc", "passes_reussies", 
                            "passes_progressives", "tacles", "interceptions", "pressions", "xg", "xa"]
            for k in numeric_keys:
                if k in curr or k in rec:
                    v_curr = curr.get(k, 0)
                    if v_curr == "N/D" or v_curr is None: v_curr = 0
                    v_rec = rec.get(k, 0)
                    if v_rec == "N/D" or v_rec is None: v_rec = 0
                    
                    if k in ["xg", "xa", "note"]:
                        merged[k] = round(float(v_curr) + float(v_rec), 2)
                    else:
                        merged[k] = int(v_curr) + int(v_rec)
            
            # Note moyenne
            c_note = curr.get("note", 0)
            r_note = rec.get("note", 0)
            if c_note == "N/D" or c_note is None or c_note == "": c_note = 0
            if r_note == "N/D" or r_note is None or r_note == "": r_note = 0
            if float(c_note) > 0 and float(r_note) > 0:
                merged["note"] = round((float(c_note) + float(r_note)) / 2, 1)
            else:
                merged["note"] = float(c_note) or float(r_note) or 0
                
            # Match count
            merged["matchs_2026"] = curr.get("matchs_2026", 0) + 1
                
            # Cartons
            c_cart = curr.get("cartons", "—")
            r_cart = rec.get("cartons", "—")
            if "Red" in (c_cart, r_cart):
                merged["cartons"] = "Red"
            elif "Yellow" in (c_cart, r_cart):
                merged["cartons"] = "Yellow"
            else:
                merged["cartons"] = "—"
                
            players[team][name] = merged
            n_players += 1
    _save(PLAYER_FILE, players)

    # 2) stats équipe (tirs/cadrés/corners/cartons) — clé home|away de la base
    stats = _load(STATS_FILE)
    key = f"{home}|{away}"
    t = summ["team"]
    cur = stats.get(key, {})
    # respecte l'orientation home/away de la base
    def pick(side, field):
        # ESPN renvoie déjà home_/away_ ; on aligne sur l'ordre de la base
        return t.get(f"{side}_{field}")
    # ESPN range ses stats en home_/away_ selon SON orientation ; on réaligne
    # sur l'orientation de notre base (le "home" de la base = home/away ESPN ?)
    espn_home_is_base_home = (t.get("home_name") == home)
    def field(base_side, name):
        espn_side = base_side if espn_home_is_base_home else ("away" if base_side == "home" else "home")
        return t.get(f"{espn_side}_{name}")
    fields = ["shots", "shots_on", "corners", "cards", "possession",
              "passes", "passes_ok", "pass_pct", "crosses", "crosses_ok",
              "long_balls", "tackles", "tackles_won", "interceptions",
              "clearances", "blocked_shots", "fouls", "offsides", "saves"]
    for f in fields:
        cur[f"home_{f}"] = field("home", f)
        cur[f"away_{f}"] = field("away", f)
    cur["source_espn"] = "ESPN (Opta) — stats joueur + équipe complètes"
    # arbitre réel + sévérité (cartons du match enregistrés pour son style)
    ref = summ.get("referee")
    if ref:
        cur["referee"] = ref
        tc = (cur.get("home_cards") or 0) + (cur.get("away_cards") or 0)
        refform.record_match(ref, tc)
    # xG : on ne touche JAMAIS à une valeur réelle déjà présente dans le fichier.
    # espn_stats.py calcule maintenant un xG estimé (shots_on×0.11 + off×0.036)
    # depuis les tirs ESPN. On l'injecte UNIQUEMENT si le match n'avait pas encore de xG.
    for side in ("home", "away"):
        existing_xg = stats.get(key, {}).get(f"{side}_xg")
        if existing_xg is None:
            # pas encore de xG : on prend l'estimation ESPN
            espn_xg = field(side, "xg")
            cur[f"{side}_xg"] = espn_xg  # peut être None si ESPN indisponible
        else:
            # valeur réelle existante (Opta/TheAnalyst) → on la préserve toujours
            cur[f"{side}_xg"] = existing_xg
    stats[key] = {k: v for k, v in cur.items() if v is not None
                  and k not in ("home_xg_estimated", "away_xg_estimated", "home_xg_from_leaders", "away_xg_from_leaders")}
    _save(STATS_FILE, stats)

    # 3) COMPOSITIONS RÉELLES (XI + formation + banc) extraites d'ESPN -> fichier
    #    lu par import_stats. Rend les compos automatiques pour CHAQUE match ingéré.
    n_xi = 0
    try:
        lus = summ.get("lineups") or {}

        def _toks(s):
            import unicodedata
            s = unicodedata.normalize("NFD", str(s or ""))
            s = "".join(c for c in s if unicodedata.category(c) != "Mn")
            stop = {"dr", "of", "the", "and", "republic", "rep", "ir", "pr"}
            return {w for w in s.lower().replace("&", " ").split() if w and w not in stop}

        def _block_for(team_name):
            tk = _toks(team_name)
            for tn, blk in lus.items():
                if tk and (tk & _toks(tn)):
                    return blk
            return None

        h_blk = _block_for(home)
        a_blk = _block_for(away)
        if (h_blk and (h_blk.get("xi") or [])) or (a_blk and (a_blk.get("xi") or [])):
            lineups = _load(LINEUP_FILE)
            entry = lineups.get(key, {})
            if h_blk and h_blk.get("xi"):
                entry["home_formation"] = h_blk.get("formation") or entry.get("home_formation")
                entry["home_xi"] = h_blk.get("xi")
                entry["home_bench"] = h_blk.get("bench") or entry.get("home_bench")
                n_xi += len(h_blk.get("xi") or [])
            if a_blk and a_blk.get("xi"):
                entry["away_formation"] = a_blk.get("formation") or entry.get("away_formation")
                entry["away_xi"] = a_blk.get("xi")
                entry["away_bench"] = a_blk.get("bench") or entry.get("away_bench")
                n_xi += len(a_blk.get("xi") or [])
            entry["source"] = "ESPN (compos réelles)"
            lineups[key] = entry
            _save(LINEUP_FILE, lineups)
    except Exception as e:
        print(f"     [warn] compos non extraites : {e}")

    # 4) ÉVÉNEMENTS DU MATCH (buteurs, cartons) -> match_events_real.json
    n_ev = 0
    try:
        if summ.get("events"):
            events_real = _load(EVENT_FILE)
            sev = summ["events"]
            cur_ev = events_real.get(key, {})
            # On conserve motm et note s'ils existent déjà
            cur_ev["goals"] = sev.get("goals") or cur_ev.get("goals") or []
            cur_ev["cards"] = sev.get("cards") or cur_ev.get("cards") or []
            cur_ev["commentary"] = sev.get("commentary") or cur_ev.get("commentary") or []
            raw_ht = summ.get("halftime")
            if raw_ht and "-" in raw_ht:
                if not espn_home_is_base_home:
                    parts = raw_ht.split("-")
                    cur_ev["halftime"] = f"{parts[1]}-{parts[0]}"
                else:
                    cur_ev["halftime"] = raw_ht
            else:
                cur_ev["halftime"] = cur_ev.get("halftime")
            if "motm" not in cur_ev or cur_ev["motm"] == "—":
                cur_ev.setdefault("motm", "—")
            cur_ev.setdefault("note", "")
            events_real[key] = cur_ev
            _save(EVENT_FILE, events_real)
            n_ev = len(cur_ev["goals"]) + len(cur_ev["cards"])
    except Exception as e:
        print(f"     [warn] événements non extraits : {e}")

    xitxt = f" + compos ({n_xi} titulaires)" if n_xi else ""
    evtxt = f" + évènements ({n_ev})" if n_ev else ""
    print(f"  ✅ {home} {ev['home_goals']}-{ev['away_goals']} {away} "
          f"| {n_players} joueurs (stats réelles ESPN){xitxt}{evtxt}")
    return True


def main():
    if len(sys.argv) >= 3:
        ingest_match(sys.argv[1], sys.argv[2])
        return
    conn = db.init_db()
    rows = conn.execute("SELECT home, away, utc_date FROM matches WHERE status='FINISHED'").fetchall()
    conn.close()
    
    # Wipe the player stats file before a full rebuild to avoid double counting
    _save(PLAYER_FILE, {})
    
    print(f"⚙️  Ingestion ESPN des stats joueur ({len(rows)} matchs terminés)…")
    ok = 0
    for r in rows:
        if ingest_match(r["home"], r["away"], _match_date(r["utc_date"])):
            ok += 1
    print(f"\n✅ {ok}/{len(rows)} matchs enrichis avec stats joueur réelles ESPN.")
    print("   Relance :  python3 -m collector.refresh")


if __name__ == "__main__":
    main()
