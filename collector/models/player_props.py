"""
Pronos JOUEURS (6 rôles) — présentés en PROBABILITÉS, pas en certitudes.

Principe ZÉRO-INVENTION :
  - On part de l'EFFECTIF RÉEL (squads_2026.json : noms + postes réels) et de la
    PRODUCTION RÉELLE des joueurs ayant déjà joué (player_stats_real.json : buts,
    passes décisives, tirs, xG, minutes, statut, cartons).
  - La "probabilité de buteur" est DÉRIVÉE du modèle : on répartit le λ buts de
    l'équipe (déjà calculé par le moteur) entre les joueurs selon (a) un poids de
    poste et (b) un bonus de forme réelle (buts/tirs/xG des matchs joués).
    => P(joueur marque ≥1) = 1 - exp(-λ_joueur). Probabilité, pas certitude.
  - Étiquetage clair dans l'UI : "probabilité modèle (poste + production réelle)".
  - Le GARDIEN à arrêts = vrai gardien titulaire + sollicitation dérivée de l'xG
    adverse (pas une stat d'arrêts, qui n'existe pas gratuitement par sélection).

Aucune statistique n'est inventée : tout %% sort d'un calcul reproductible.
"""
from __future__ import annotations
from math import exp

# poids de propension à MARQUER par poste (heuristique de structure, pas une stat
# par joueur : un attaquant marque plus qu'un défenseur — fait universel du foot)
SCORE_W = {
    "AC": 1.00, "BU": 1.00, "ATT": 1.00, "AG": 0.80, "AD": 0.80, "AILIER": 0.80,
    "MO": 0.55, "AM": 0.55, "MC": 0.30, "MDC": 0.18, "MD": 0.30,
    "DC": 0.12, "DD": 0.10, "DG": 0.10, "PISTON": 0.14,
    # codes génériques (squads des équipes pas encore en lice : GK/DF/MF/FW)
    "FW": 0.85, "MF": 0.32, "DF": 0.10,
    "GK": 0.0, "GB": 0.0,
}
# propension à DÉLIVRER une passe décisive / créer
ASSIST_W = {
    "MO": 1.00, "AM": 1.00, "AG": 0.90, "AD": 0.90, "AILIER": 0.90,
    "MC": 0.65, "AC": 0.55, "BU": 0.55, "DD": 0.45, "DG": 0.45, "PISTON": 0.5,
    "MDC": 0.35, "MD": 0.5, "DC": 0.15,
    # codes génériques
    "FW": 0.6, "MF": 0.7, "DF": 0.2, "GK": 0.02, "GB": 0.02,
}


def _last(name):
    """Nom de famille (pour matcher XI '... (GK)' vs nom complet du squad)."""
    if not name:
        return ""
    s = str(name).split("(")[0].strip()
    return s.split()[-1].lower() if s else ""


def _norm_pos(poste):
    if not poste:
        return ""
    return str(poste).upper().split("/")[0].split("-")[0].strip()


def _weight(poste, table):
    p = _norm_pos(poste)
    for key, w in table.items():
        if p.startswith(key):
            return w
    return 0.25


def _to_num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _player_real(stats_team, name):
    """Récupère la prod réelle d'un joueur (dict) si présente, sinon {}."""
    if not isinstance(stats_team, dict):
        return {}
    return stats_team.get(name) or {}


def compute(team, roster, lam_team, lam_opp, stats_team=None, lineup_xi=None):
    """
    team       : nom équipe
    roster     : liste de joueurs réels [{joueur, poste, statut, ...}] (squads)
    lam_team   : buts attendus de l'équipe (du moteur)
    lam_opp    : buts attendus de l'adversaire (pour la sollicitation du gardien)
    stats_team : dict {nom: stats réelles} (matchs joués) ou None
    lineup_xi  : liste de noms du XI réel si dispo (sinon None)
    Retour : dict des 6 rôles, chacun en probabilités + explication.
    """
    stats_team = stats_team or {}
    xi_set = set(_last(n) for n in (lineup_xi or []))
    players = []
    for pl in (roster or []):
        name = pl.get("joueur") or pl.get("name")
        if not name:
            continue
        poste = pl.get("poste")
        rp = _player_real(stats_team, name)
        statut = rp.get("statut") or pl.get("statut")
        # un joueur est "probable titulaire" s'il est dans le XI réel connu,
        # ou s'il a déjà été titulaire (donnée réelle) ; sinon rotation/banc.
        starter = (_last(name) in xi_set) if len(xi_set) >= 8 else (statut == "Titulaire")
        played = bool(rp) or (_last(name) in xi_set)
        players.append({"name": name, "poste": poste, "real": rp,
                        "statut": statut, "starter": starter, "played": played})

    # si on connaît le XI réel ou des titulaires réels, on se restreint aux joueurs
    # pertinents (titulaires + remplaçants ayant joué) pour ne pas diluer sur 26 noms
    if len(xi_set) >= 8:
        relevant = [p for p in players if p["starter"]]
    else:
        relevant = [p for p in players if p["starter"] or p["played"]]
    if len(relevant) >= 8:
        players = relevant

    if not players:
        return None

    # ---- poids buteur : poste + bonus production réelle ----
    def scorer_strength(p):
        w = _weight(p["poste"], SCORE_W)
        r = p["real"]
        goals = _to_num(r.get("buts")) or 0
        shots = _to_num(r.get("tirs")) or 0
        xg = _to_num(r.get("xg")) or 0
        # bonus borné : la production réelle renforce, sans écraser le poste
        bonus = 1.0 + min(1.5, 0.5 * goals + 0.12 * shots + 0.6 * xg)
        start = 1.0 if p.get("starter") else 0.45     # titulaires pèsent plus
        return w * bonus * start

    str_sum = sum(scorer_strength(p) for p in players) or 1.0
    scorers = []
    for p in players:
        share = scorer_strength(p) / str_sum
        lam_p = lam_team * share
        prob = 1 - exp(-lam_p)                      # P(marque ≥ 1)
        if prob > 0.01:
            scorers.append({"name": p["name"], "poste": p["poste"],
                            "p": round(prob, 4),
                            "real_goals": _to_num(p["real"].get("buts")),
                            "why": _scorer_why(p)})
    scorers.sort(key=lambda x: x["p"], reverse=True)

    # ---- passeur / créateur ----
    def assist_strength(p):
        w = _weight(p["poste"], ASSIST_W)
        r = p["real"]
        ast = _to_num(r.get("passes_dec")) or 0
        start = 1.0 if p.get("starter") else 0.45
        return w * (1.0 + min(1.2, 0.6 * ast)) * start

    a_sum = sum(assist_strength(p) for p in players) or 1.0
    assisters = []
    for p in players:
        share = assist_strength(p) / a_sum
        lam_a = lam_team * 0.7 * share              # ~0.7 passe déc. par but
        prob = 1 - exp(-lam_a)
        if prob > 0.01:
            assisters.append({"name": p["name"], "poste": p["poste"],
                              "p": round(prob, 4),
                              "real_assists": _to_num(r := p["real"].get("passes_dec")),
                              "why": _assist_why(p)})
    assisters.sort(key=lambda x: x["p"], reverse=True)

    # ---- gardien le plus sollicité (vrai GK + xG adverse) ----
    gk = next((p for p in players if _norm_pos(p["poste"]) in ("GK", "GB")), None)
    # tirs cadrés adverses attendus ≈ xG adverse / 0.32 (un tir cadré ~0.32 xG)
    exp_sot_faced = round(lam_opp / 0.32, 1) if lam_opp else None
    keeper = None
    if gk:
        keeper = {"name": gk["name"],
                  "expSotFaced": exp_sot_faced,
                  "fromLineup": bool(lineup_xi and gk["name"] in lineup_xi),
                  "why": f"Subit une pression offensive adverse de ~{lam_opp} xG "
                         f"→ environ {exp_sot_faced} tirs cadrés à gérer."
                         if exp_sot_faced else "Sollicitation N/D."}

    # ---- remplaçant à impact (vrais remplaçants productifs, sinon profils) ----
    bench_impact = []
    for p in players:
        r = p["real"]
        if (r.get("statut") == "Remplaçant"):
            g = _to_num(r.get("buts")) or 0
            a = _to_num(r.get("passes_dec")) or 0
            if g or a:
                bench_impact.append({
                    "name": p["name"], "poste": p["poste"],
                    "goals": g, "assists": a,
                    "why": "Entré en jeu et décisif : "
                           + ", ".join(filter(None, [
                               f"{int(g)} but(s)" if g else "",
                               f"{int(a)} passe(s) déc." if a else ""])) + "."})
    bench_impact.sort(key=lambda x: (x["goals"], x["assists"]), reverse=True)

    return {
        "scorers": scorers[:5],
        "assisters": assisters[:4],
        "creator": assisters[0] if assisters else None,
        "keeper": keeper,
        "benchImpact": bench_impact[:3],
        "note": "Probabilités MODÈLE (poste réel + production réelle des matchs joués), "
                "pas des certitudes. Se précisent à mesure que les équipes jouent.",
    }


def _scorer_why(p):
    pos = _norm_pos(p["poste"])
    r = p["real"]
    g = _to_num(r.get("buts")) or 0
    shots = _to_num(r.get("tirs")) or 0
    bits = []
    if g:
        bits.append(f"déjà {int(g)} but(s) dans le tournoi")
    if shots >= 3:
        bits.append(f"volume de tirs élevé ({int(shots)})")
    if pos.startswith(("AC", "BU", "ATT")):
        bits.append("attaquant de pointe")
    elif pos.startswith(("AG", "AD")):
        bits.append("ailier tranchant")
    elif pos.startswith(("MO", "AM")):
        bits.append("projection depuis le milieu")
    return " · ".join(bits) if bits else "présence offensive selon le poste"


def _assist_why(p):
    pos = _norm_pos(p["poste"])
    r = p["real"]
    a = _to_num(r.get("passes_dec")) or 0
    bits = []
    if a:
        bits.append(f"déjà {int(a)} passe(s) déc.")
    if pos.startswith(("MO", "AM")):
        bits.append("meneur de jeu")
    elif pos.startswith(("AG", "AD")):
        bits.append("centres depuis l'aile")
    elif pos.startswith(("DD", "DG", "PISTON")):
        bits.append("apport offensif du couloir")
    return " · ".join(bits) if bits else "création selon le poste"
