"""
Ingestion des COMPOSITIONS OFFICIELLES (XI) pour les matchs À VENIR.

ESPN publie le XI réel ~1 h avant le coup d'envoi. On le récupère et on le range
dans matches.events_json -> lineups.{home_xi, away_xi, home_formation, ...}
afin que le pipeline applique la pondération des absences (availability.py).

RÈGLE N°1 — ZÉRO INVENTION : on n'écrit le XI QUE s'il est réellement publié par
ESPN (≥ 11 titulaires par équipe). Sinon on ne touche à rien.

Usage :
  python3 -m collector.lineup_ingest                # tous les matchs SCHEDULED proches
  python3 -m collector.lineup_ingest "France" "Senegal"
"""
from __future__ import annotations
import json, sys
from collector.db import database as db
from collector.sources import espn_stats as espn


def _norm(s):
    import unicodedata
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower().strip()


def _match_lineup_to_sides(lineups, home, away):
    """Associe les blocs ESPN (clé = nom normalisé) aux côtés home/away."""
    hk = _norm(home).split()[-1]
    ak = _norm(away).split()[-1]
    h_block = a_block = None
    for team_norm, blk in (lineups or {}).items():
        if hk in team_norm:
            h_block = blk
        elif ak in team_norm:
            a_block = blk
    return h_block, a_block


def ingest_lineup(home, away):
    """Tente de récupérer le XI officiel d'un match à venir. Retourne True si écrit."""
    ev = espn.find_event(home, away)
    if not ev:
        return False, "événement ESPN introuvable"
    summ = espn.match_summary(ev["id"])
    if not summ:
        return False, "résumé ESPN indisponible"
    h_block, a_block = _match_lineup_to_sides(summ.get("lineups"), home, away)
    h_xi = (h_block or {}).get("xi") or []
    a_xi = (a_block or {}).get("xi") or []
    if len(h_xi) < 11 or len(a_xi) < 11:
        return False, f"XI pas encore publié (dom {len(h_xi)}/11, ext {len(a_xi)}/11)"

    conn = db.init_db()
    row = conn.execute(
        "SELECT id, events_json FROM matches WHERE home=? AND away=?",
        (home, away)).fetchone()
    if not row:
        conn.close()
        return False, "match absent de la base"
    try:
        events = json.loads(row["events_json"]) if row["events_json"] else {}
    except (TypeError, ValueError):
        events = {}
    lu = events.get("lineups") or {}
    lu.update({
        "home_xi": h_xi, "away_xi": a_xi,
        "home_formation": (h_block or {}).get("formation") or lu.get("home_formation"),
        "away_formation": (a_block or {}).get("formation") or lu.get("away_formation"),
        "source_xi": "ESPN (compo officielle)",
    })
    events["lineups"] = lu
    conn.execute("UPDATE matches SET events_json=? WHERE id=?",
                 (json.dumps(events, ensure_ascii=False), row["id"]))
    conn.commit()
    conn.close()
    return True, f"XI ingéré (dom {len(h_xi)}, ext {len(a_xi)})"


def ingest_all_upcoming(limit_days=2):
    """Parcourt les matchs SCHEDULED proches et tente d'ingérer leur XI."""
    conn = db.init_db()
    rows = conn.execute(
        "SELECT home, away FROM matches WHERE status='SCHEDULED' ORDER BY utc_date LIMIT 30"
    ).fetchall()
    conn.close()
    done = 0
    for r in rows:
        ok, msg = ingest_lineup(r["home"], r["away"])
        flag = "✅" if ok else "·"
        print(f"  {flag} {r['home']} vs {r['away']} — {msg}")
        if ok:
            done += 1
    print(f"\n{done} composition(s) officielle(s) ingérée(s).")
    return done


def main():
    if len(sys.argv) >= 3:
        ok, msg = ingest_lineup(sys.argv[1], sys.argv[2])
        print(("✅ " if ok else "· ") + msg)
    else:
        ingest_all_upcoming()


if __name__ == "__main__":
    main()
