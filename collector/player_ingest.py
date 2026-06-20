#!/usr/bin/env python3
"""
Ingesteur de STATS JOUEUR pour la CDM 2026 — le "remplissage live".

Tant qu'aucun match 2026 n'a de données d'events publiques, les stats joueur
restent N/D. Dès qu'un match est disponible (StatsBomb open data 2026, ou un export
manuel au format attendu), ce script :
  1. calcule le rapport joueur par joueur (depuis une source d'events 2026),
  2. insère chaque ligne dans la base (player_match_stats),
  3. met à jour les cumuls par joueur (players),
  4. ré-exporte les effectifs enrichis pour l'app web.

Deux modes d'alimentation :
  --statsbomb <match_id>   : si la CDM 2026 entre dans StatsBomb open data
  --file <report.json>     : ingérer un rapport déjà calculé (format documenté ci-dessous)

Export :
  python3 -m collector.player_ingest --export   # data/squads_2026.json (pour l'app)
"""
from __future__ import annotations
import sys, os, json, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector.db import database as db
from collector.sources import player_bios as _bios

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _to_match_stat(p: dict, team: str, match_ref: str) -> dict:
    """Mappe une ligne de rapport joueur -> colonnes player_match_stats."""
    def i(x):
        return 0 if x in (None, "N/D") else int(x)
    def f(x):
        return 0.0 if x in (None, "N/D") else float(x)
    return {
        "player_name": p["joueur"], "team": team, "match_ref": match_ref,
        "minutes": i(p.get("minutes")), "goals": i(p.get("buts")),
        "assists": i(p.get("passes_dec")), "shots": i(p.get("tirs")),
        "shots_on": i(p.get("tirs_cadres")), "xg": f(p.get("xg")), "xa": f(p.get("xa")),
        "passes": i(p.get("passes_reussies")), "prog_passes": i(p.get("passes_progressives")),
        "tackles": i(p.get("tacles")), "interceptions": i(p.get("interceptions")),
        "blocks": i(p.get("blocks")), "clearances": i(p.get("degagements")),
        "pressures": i(p.get("pressions")), "recoveries": i(p.get("ballons_recuperes")),
        "fouls": i(p.get("fautes_commises")), "fouls_served": i(p.get("fautes_subies")),
        "offsides": i(p.get("hors_jeu")), "own_goals": i(p.get("but_csc", 0)),
        "sub_ins": 1 if p.get("statut") == "Remplaçant" and p.get("minutes", 0) > 0 else 0,
        "cards": "" if p.get("cartons") in ("—", None) else p.get("cartons"),
    }


def ingest_report(report: dict, match_ref: str) -> int:
    """Insère un rapport (format rapport joueur) dans la base. Renvoie nb joueurs ingérés."""
    conn = db.init_db()
    n = 0
    for p in report.get("players", []):
        st = _to_match_stat(p, p.get("equipe", "?"), match_ref)
        if db.add_player_match(conn, **st):
            n += 1
    conn.commit(); conn.close()
    return n


def ingest_statsbomb(match_id: int) -> int:
    """
    Pour le futur : dès qu'un match CDM 2026 entre dans une source d'events
    (format StatsBomb), fournis un rapport JSON via --file. Cette fonction
    n'utilise aucune donnée 2018/2022.
    """
    print("  [info] mode StatsBomb désactivé (aucune source d'events 2026 branchée).")
    print("         Utilise --file <rapport.json> pour ingérer un match 2026.")
    return 0


def _load_real_player_stats():
    """Charge les vraies stats joueur collectées (notes/buts/passes des matchs joués)."""
    p = os.path.join(DATA_DIR, "player_stats_real.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


def _match_player(real_team: dict, name: str):
    """Retrouve un joueur dans les stats réelles par correspondance souple de nom."""
    if name in real_team:
        return real_team[name]
    # correspondance sur le nom de famille (dernier mot)
    last = name.split()[-1].lower()
    for rname, stats in real_team.items():
        if rname.split()[-1].lower() == last:
            return stats
    return None


def export_for_web():
    """Exporte les effectifs 2026 + stats (réelles si dispo, sinon N/D) pour l'app."""
    conn = db.init_db()
    teams = db.all_player_teams(conn)
    real = _load_real_player_stats()
    n_real_players = 0
    out = []
    for t in teams:
        players = []
        real_team = real.get(t, {})
        for r in db.players_by_team(conn, t):
            played = r["matches_2026"] > 0
            rs = _match_player(real_team, r["name"]) if real_team else None
            if rs:
                n_real_players += 1
            def val(db_val, real_key):
                # priorité : stat réelle collectée > cumul base > N/D
                if rs and real_key in rs:
                    return rs[real_key]
                return db_val if played else "N/D"
            players.append({
                "numero": r["number"], "joueur": r["name"], "poste": r["pos"],
                "age": r["age"], "matchs_2026": r["matches_2026"] or (1 if rs else 0),
                "statut": (rs.get("statut", "—") if rs else "N/D"),
                "minutes": val(r["minutes_2026"], "minutes"),
                "buts": val(r["goals"], "buts"), "passes_dec": val(r["assists"], "passes_dec"),
                "but_csc": val(r["own_goals"], "but_csc"),
                "tirs": val(r["shots"], "tirs"), "tirs_cadres": val(r["shots_on"], "tirs_cadres"),
                "xg": val(round(r["xg"], 2), "xg"), "xa": val(round(r["xa"], 2), "xa"),
                "passes_reussies": val(r["passes"], "passes_reussies"),
                "passes_progressives": val(r["prog_passes"], "passes_progressives"),
                "tacles": val(r["tackles"], "tacles"), "interceptions": val(r["interceptions"], "interceptions"),
                "blocks": val(r["blocks"], "blocks"), "degagements": val(r["clearances"], "degagements"),
                "pressions": val(r["pressures"], "pressions"), "ballons_recuperes": val(r["recoveries"], "ballons_recuperes"),
                "fautes_commises": val(r["fouls"], "fautes_commises"),
                "fautes_subies": val(r["fouls_served"], "fautes_subies"),
                "hors_jeu": val(r["offsides"], "hors_jeu"),
                "remplacements": val(r["sub_ins"], "sub_ins"),
                "note": rs.get("note", "N/D") if rs else "N/D",
                "cartons": (rs.get("cartons") if rs and rs.get("cartons") else
                            ("—" if rs else ((r["cards"].strip() or "—") if played else "N/D"))),
                "bio": _bios.get_bio(r["name"]),   # profil réel sourcé ou None (=> N/D)
            })
        out.append({"equipe": t, "joueurs": players})
    conn.close()
    path = os.path.join(DATA_DIR, "squads_2026.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    total = sum(len(t["joueurs"]) for t in out)
    played = sum(1 for t in out for p in t["joueurs"] if p["matchs_2026"] > 0)
    print(f"✅ export : {len(out)} sélections, {total} joueurs -> {path}")
    print(f"   ({played} joueurs avec stats 2026 réelles ; les autres = N/D en attendant leurs matchs)")


def main():
    ap = argparse.ArgumentParser(description="Ingesteur stats joueur CDM 2026")
    ap.add_argument("--statsbomb", type=int, help="ingérer un match_id StatsBomb (CDM 2026)")
    ap.add_argument("--file", help="ingérer un rapport JSON (format rapport joueur)")
    ap.add_argument("--ref", default="manual", help="référence du match (avec --file)")
    ap.add_argument("--export", action="store_true", help="exporter squads_2026.json pour l'app")
    args = ap.parse_args()

    if args.statsbomb:
        n = ingest_statsbomb(args.statsbomb)
        print(f"✅ {n} joueurs ingérés depuis StatsBomb match {args.statsbomb}")
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            rep = json.load(f)
        n = ingest_report(rep, args.ref)
        print(f"✅ {n} joueurs ingérés depuis {args.file}")
    if args.export or not (args.statsbomb or args.file):
        export_for_web()


if __name__ == "__main__":
    main()
