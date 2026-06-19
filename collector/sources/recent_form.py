"""
Forme récente RÉELLE des sélections (10 derniers matchs avant/pendant la CDM 2026).

Source : collector/data/recent_form.json (collecté sur le web : 11v11, Goal, AiScore...).
Chaque match = [adversaire, lieu(H/A), buts_pour, buts_contre, W/D/L, compétition].

Sert à :
  1. calculer une vraie FORME (points sur 10 matchs, buts marqués/encaissés moyens)
     -> calibre le modèle (λ) au lieu du seul rating FIFA.
  2. fournir la chaîne W/D/L pour l'affichage (5 derniers) dans le dashboard.

Pour les équipes non encore documentées à la main, on DÉRIVE une forme plausible
à partir du vrai rating FIFA (clairement marquée "estimée" via le champ 'source').
"""
from __future__ import annotations
import os, json

DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "recent_form.json")


def load() -> dict:
    if not os.path.exists(DATA):
        return {}
    with open(DATA, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


# ---- intégration des matchs CDM 2026 déjà joués dans la forme récente ----
_CDM_CACHE = None


def _cdm_results():
    """
    Lit les résultats CDM 2026 terminés depuis la base et les met au format forme :
    {équipe: [[adversaire, H/A, gf, ga, W/D/L, 'CDM 2026'], ...]} (plus récent d'abord).
    Ainsi la 'forme des 10 derniers' inclut automatiquement le 1er tour de la CDM.
    """
    global _CDM_CACHE
    if _CDM_CACHE is not None:
        return _CDM_CACHE
    out = {}
    try:
        from collector.db import database as db
        conn = db.connect()
        rows = conn.execute(
            "SELECT home, away, home_goals, away_goals, utc_date FROM matches "
            "WHERE status='FINISHED' AND home_goals IS NOT NULL ORDER BY utc_date DESC"
        ).fetchall()
        conn.close()
        for r in rows:
            hg, ag = r["home_goals"], r["away_goals"]
            hres = "W" if hg > ag else ("L" if hg < ag else "D")
            ares = "W" if ag > hg else ("L" if ag < hg else "D")
            out.setdefault(r["home"], []).append([r["away"], "H", hg, ag, hres, "CDM 2026"])
            out.setdefault(r["away"], []).append([r["home"], "A", ag, hg, ares, "CDM 2026"])
    except Exception:
        out = {}
    _CDM_CACHE = out
    return out


def team_form(team: str) -> dict | None:
    """
    Résumé de forme — UNIQUEMENT à partir de données RÉELLES (recent_form.json).
    Renvoie None si l'équipe n'a pas de vraies données (pas d'estimation : on
    n'invente jamais de scores).
      - pts10, gf_avg, ga_avg, last5 ("WWDWL"), form_index (0..1), source
    """
    data = load()
    pre = data.get(team) or []          # forme d'avant-tournoi (amicaux/qualifs)
    cdm = _cdm_results().get(team) or [] # matchs CDM 2026 déjà joués (plus récents)
    # CDM en TÊTE (plus récent), puis on complète avec l'historique pré-tournoi, max 10
    matches = (cdm + pre)[:10]
    if not matches:
        return None        # zéro estimé : on préfère N/D à une donnée inventée
    n = len(matches)
    pts = gf = ga = 0
    last5 = []
    for i, m in enumerate(matches):
        _, _, f, a, res, _ = m
        gf += f; ga += a
        pts += 3 if res == "W" else 1 if res == "D" else 0
        if i < 5:
            last5.append(res)
    max_pts = 3 * n
    return {
        "pts10": pts, "played": n,
        "gf_avg": round(gf / n, 2), "ga_avg": round(ga / n, 2),
        "last5": "".join(last5),
        "form_index": round(pts / max_pts, 3) if max_pts else 0.5,
        "cdmGames": len(cdm),
        "source": (f"réelle (10 derniers · {len(cdm)} de la CDM 2026)" if cdm
                   else "réelle (10 derniers)"),
    }


def all_forms() -> dict:
    return {t: team_form(t) for t in load().keys()}
