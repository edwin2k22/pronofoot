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

from collector.models import commentary_profiles as cprof

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


def compute(team, roster, lam_team, lam_opp, stats_team=None, lineup_xi=None,
            event_profile=None, exp_team_shots=None, exp_team_sot=None,
            exp_team_fouls=None):
    """
    team       : nom équipe
    roster     : liste de joueurs réels [{joueur, poste, statut, ...}] (squads)
    lam_team   : buts attendus de l'équipe (du moteur)
    lam_opp    : buts attendus de l'adversaire (pour la sollicitation du gardien)
    stats_team : dict {nom: stats réelles} (matchs joués) ou None
    lineup_xi  : liste de noms du XI réel si dispo (sinon None)
    event_profile : profil commentaires equipe/adversaire (tirs, fautes, etc.)
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

    volume_props = _volume_props(players, event_profile, exp_team_shots, exp_team_sot, exp_team_fouls)

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
        "shotProps": volume_props["shots"],
        "shotOnProps": volume_props["shotsOn"],
        "creatorProps": volume_props["creators"],
        "foulProps": volume_props["fouls"],
        "matchup": volume_props["matchup"],
        "keeper": keeper,
        "benchImpact": bench_impact[:3],
        "note": "Probabilités MODÈLE (poste réel + production réelle des matchs joués), "
                "pas des certitudes. Se précisent à mesure que les équipes jouent.",
    }


def _rate_per90(total, minutes, fallback_games=0):
    total = _to_num(total) or 0
    minutes = _to_num(minutes) or 0
    if minutes >= 30:
        return total / minutes * 90.0
    games = _to_num(fallback_games) or 0
    if games > 0:
        return total / games
    return None


def _poisson_over(lam, line):
    lam = max(0.0, float(lam or 0))
    if line <= 0.5:
        return 1 - exp(-lam)
    if line <= 1.5:
        return 1 - exp(-lam) * (1 + lam)
    return 1 - exp(-lam) * (1 + lam + (lam * lam / 2.0))


def _factor(profile, key):
    return ((profile or {}).get("factors") or {}).get(key, 1.0) or 1.0


def _matchup_label(factor):
    if factor >= 1.15:
        return "matchup favorable"
    if factor <= 0.88:
        return "matchup ferme"
    return "matchup neutre"


def _base_rate(p, event_profile, stat_key, event_key, pos_table=None):
    r = p["real"]
    ev = cprof.player_event_stats(event_profile, p["name"])
    minutes = _to_num(r.get("minutes")) or 0
    real_rate = _rate_per90(r.get(stat_key), minutes, r.get("matchs_2026"))
    event_rate = _rate_per90(ev.get(event_key), minutes, (event_profile or {}).get("sample"))
    rates = [v for v in (real_rate, event_rate) if v is not None]
    if rates:
        return max(rates)
    if pos_table:
        return _weight(p["poste"], pos_table) * 1.6
    return 0.25


def _volume_props(players, event_profile, exp_team_shots, exp_team_sot, exp_team_fouls):
    sample = (event_profile or {}).get("sample", 0)
    shot_factor = _factor(event_profile, "shots")
    sot_factor = _factor(event_profile, "shotsOn")
    foul_factor = _factor(event_profile, "fouls")
    team = (event_profile or {}).get("team") or {}

    def expected_total(explicit, fallback_field, factor, default):
        if explicit is not None:
            return max(0.2, float(explicit))
        base = team.get(fallback_field) or default
        return max(0.2, float(base) * factor)

    team_shots = expected_total(exp_team_shots, "shotsFor", shot_factor, 10.5)
    team_sot = expected_total(exp_team_sot, "shotsOnFor", sot_factor, 3.4)
    team_fouls = expected_total(exp_team_fouls, "foulsCommitted", foul_factor, 10.0)

    def start_factor(p):
        return 1.0 if p.get("starter") else 0.45

    def shot_strength(p):
        pos = _weight(p["poste"], SCORE_W)
        if pos <= 0.02:
            return 0.0
        rate = _base_rate(p, event_profile, "tirs", "shots", SCORE_W)
        return max(0.01, (0.60 * pos + 0.40 * min(rate / 3.0, 2.0)) * start_factor(p))

    def sot_strength(p):
        pos = _weight(p["poste"], SCORE_W)
        if pos <= 0.02:
            return 0.0
        rate = _base_rate(p, event_profile, "tirs_cadres", "shotsOn", SCORE_W)
        return max(0.01, (0.45 * pos + 0.55 * min(rate / 1.4, 2.0)) * start_factor(p))

    def creator_strength(p):
        pos = _weight(p["poste"], ASSIST_W)
        ev = cprof.player_event_stats(event_profile, p["name"])
        minutes = _to_num(p["real"].get("minutes")) or 0
        created_rate = _rate_per90(ev.get("createdShots"), minutes, sample) or 0
        assists = _to_num(p["real"].get("passes_dec")) or 0
        return max(0.01, (0.65 * pos + 0.25 * min(created_rate / 2.0, 2.0) + 0.10 * min(assists, 3)) * start_factor(p))

    def foul_strength(p):
        r = p["real"]
        ev = cprof.player_event_stats(event_profile, p["name"])
        minutes = _to_num(r.get("minutes")) or 0
        real_rate = _rate_per90(r.get("fautes_commises"), minutes, r.get("matchs_2026")) or 0
        event_rate = _rate_per90(ev.get("foulsCommitted"), minutes, sample) or 0
        pos = _norm_pos(p["poste"])
        pos_bonus = 0.9 if pos.startswith(("DC", "DD", "DG", "MDC", "DF", "CD", "LB", "RB")) else 0.45
        return max(0.01, (max(real_rate, event_rate) + pos_bonus) * start_factor(p))

    def distribute(strength_fn, team_total, prop_kind=""):
        strengths = [(p, strength_fn(p)) for p in players]
        strengths = [(p, s) for p, s in strengths if s > 0]
        total = sum(s for _, s in strengths) or 1.0
        out = []
        for p, strength in strengths:
            ev = cprof.player_event_stats(event_profile, p["name"])
            expected = max(0.0, team_total * strength / total)
            out.append({
                "name": p["name"],
                "poste": p["poste"],
                "expected": round(expected, 2),
                "p05": round(_poisson_over(expected, 0.5), 4),
                "p15": round(_poisson_over(expected, 1.5), 4),
                "why": _prop_reason(p, ev, expected, prop_kind),
            })
        out.sort(key=lambda x: (x["p05"], x["expected"]), reverse=True)
        return out

    return {
        "shots": distribute(shot_strength, team_shots, prop_kind="shots")[:5],
        "shotsOn": distribute(sot_strength, team_sot, prop_kind="shotsOn")[:4],
        "creators": distribute(creator_strength, max(0.4, team_shots * 0.55), prop_kind="created")[:4],
        "fouls": distribute(foul_strength, team_fouls, prop_kind="fouls")[:4],
        "matchup": {
            "sample": sample,
            "shotFactor": shot_factor,
            "shotLabel": _matchup_label(shot_factor),
            "sotFactor": sot_factor,
            "sotLabel": _matchup_label(sot_factor),
            "foulFactor": foul_factor,
            "foulLabel": _matchup_label(foul_factor),
            "teamShots": round(team_shots, 1),
            "teamShotsOn": round(team_sot, 1),
        },
    }


def _prop_reason(p, ev, expected, kind):
    bits = []
    if kind == "shots":
        shots = _to_num(p["real"].get("tirs")) or _to_num(ev.get("shots")) or 0
        if shots:
            bits.append(f"{int(shots)} tir(s) deja vus")
    elif kind == "shotsOn":
        sot = _to_num(p["real"].get("tirs_cadres")) or _to_num(ev.get("shotsOn")) or 0
        if sot:
            bits.append(f"{int(sot)} cadre(s) deja vus")
    elif kind == "created":
        created = _to_num(ev.get("createdShots")) or 0
        if created:
            bits.append(f"{int(created)} passe(s) avant tir")
    elif kind == "fouls":
        fouls = _to_num(p["real"].get("fautes_commises")) or _to_num(ev.get("foulsCommitted")) or 0
        if fouls:
            bits.append(f"{int(fouls)} faute(s) commises")
    if p.get("starter"):
        bits.append("role titulaire")
    bits.append(f"projection {expected:.1f}")
    return " · ".join(bits)


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
