"""
Modèles SÉPARÉS (un par marché), maintenant adossés à la grille de scores CORRIGÉE
(Dixon-Coles + Poisson bivarié, voir score_grid.py) — fini le Poisson naïf.

  1) result_model  : 1 / N / 2   (grille corrigée + ancrage Elo)
  2) goals_model   : Over/Under 2.5, BTTS, Under 1.5, score probable
  3) corners_model : Over/Under corners
  4) cards_model   : Over/Under cartons
"""
from __future__ import annotations
from math import exp, factorial
from .elo import expected_score, HOME_ADV_ELO
from . import score_grid as sg


def _poisson(k, lam):
    return exp(-lam) * lam ** k / factorial(k)


# ---------- 1) RÉSULTAT (1 N 2) ----------
def result_model(elo_h, elo_a, lam_h, lam_a, elo_weight=0.5,
                 rho=sg.DEFAULT_RHO, gamma=0.0, grid=None):
    """
    Combine la grille de scores CORRIGÉE (Dixon-Coles + bivarié) avec l'ancrage Elo.
    grid : grille pré-calculée (optionnelle) pour éviter de la recalculer.
    """
    if grid is None:
        grid = sg.score_grid(lam_h, lam_a, rho, gamma)
    o = sg.outcomes(grid)
    p1, px, p2 = o["p1"], o["pX"], o["p2"]

    # ancrage Elo (probabilité de NE PAS perdre, nul gardé de la grille corrigée)
    e_h = expected_score(elo_h, elo_a, HOME_ADV_ELO)
    draw_base = px
    e1 = e_h * (1 - draw_base)
    e2 = (1 - e_h) * (1 - draw_base)

    w = elo_weight
    return {
        "p1": round((1 - w) * p1 + w * e1, 4),
        "pX": round((1 - w) * px + w * draw_base, 4),
        "p2": round((1 - w) * p2 + w * e2, 4),
    }


# ---------- 2) BUTS ----------
def goals_model(lam_h, lam_a, line=2.5, rho=sg.DEFAULT_RHO, gamma=0.0, grid=None):
    if grid is None:
        grid = sg.score_grid(lam_h, lam_a, rho, gamma)
    o = sg.outcomes(grid)
    return {
        "over": o["over25"], "under": o["under25"],
        "btts": o["btts"], "under15": o["under15"],
        "top_score": o["top_score"],
        "exp_goals": round(lam_h + lam_a, 2),
    }


# ---------- 3) CORNERS ----------
def corners_model(corners_h, corners_a, line=None):
    """Total de corners ~ Poisson(λ = corners attendus des 2 équipes).
    Les lignes O/U sont DYNAMIQUES : centrées sur le total attendu du match
    (sinon, avec ~17 corners attendus, toutes les lignes basses seraient à ~99%)."""
    lam = max(corners_h + corners_a, 1.0)
    # ligne principale = total attendu arrondi au .5 inférieur (ex. 17.3 -> 16.5)
    center = round(lam - 0.5) + 0.5
    if line is None:
        line = center
    over = sum(_poisson(k, lam) for k in range(int(line) + 1, 60))
    out = {"exp_corners": round(lam, 1), "over": round(over, 4),
           "under": round(1 - over, 4), "line": line,
           "home": round(corners_h, 1), "away": round(corners_a, 1)}
    # 4 lignes O/U encadrant le total attendu (center ±1.5)
    lines = {}
    for ln in (center-2, center-1, center, center+1, center+2):
        if ln < 1.5:
            continue
        o = sum(_poisson(k, lam) for k in range(int(ln) + 1, 60))
        lines[str(ln)] = {"over": round(o, 4), "under": round(1 - o, 4)}
    out["lines"] = lines
    return out


# ---------- 3bis) TIRS & TIRS CADRÉS ----------
def shots_model(shots_h, shots_a, son_h, son_a):
    """
    Prédiction des tirs et tirs cadrés (matchs à venir).
    Entrées = tirs/tirs-cadrés attendus par équipe (moyennes évolutives shrinkées,
    croisant l'attaque d'une équipe et la défense adverse). Tout dérive de stats RÉELLES.

    - exp_shots / exp_shots_on : total attendu du match
    - lines : Over/Under multi-lignes sur le TOTAL de tirs (centrées sur l'attendu)
    - linesOn : Over/Under multi-lignes sur le TOTAL de tirs cadrés
    - homeAcc / awayAcc : précision attendue (cadrés / tirs) par équipe
    """
    sh_h = max(shots_h, 0.5)
    sh_a = max(shots_a, 0.5)
    so_h = max(min(son_h, sh_h), 0.2)
    so_a = max(min(son_a, sh_a), 0.2)
    tot_shots = sh_h + sh_a
    tot_on = so_h + so_a

    def _lines(lam, spread, step=2):
        center = round(lam - 0.5) + 0.5
        out = {}
        for ln in (center - 2*step, center - step, center, center + step, center + 2*step):
            if ln < 1.5:
                continue
            o = sum(_poisson(k, lam) for k in range(int(ln) + 1, 80))
            out[str(ln)] = {"over": round(o, 4), "under": round(1 - o, 4)}
        return out, center

    lines, center = _lines(tot_shots, spread=2, step=2)
    lines_on, center_on = _lines(tot_on, spread=1, step=1)

    def _acc(s, so):
        return round(so / s * 100) if s > 0 else None

    return {
        "expShots": round(tot_shots, 1),
        "expShotsOn": round(tot_on, 1),
        "home": round(sh_h, 1), "away": round(sh_a, 1),
        "homeOn": round(so_h, 1), "awayOn": round(so_a, 1),
        "homeAcc": _acc(sh_h, so_h), "awayAcc": _acc(sh_a, so_a),
        "line": center, "lineOn": center_on,
        "lines": lines, "linesOn": lines_on,
    }


# ---------- 4) CARTONS ----------
def cards_model(cards_h, cards_a, line=3.5, fouls_h=None, fouls_a=None):
    lam = max(cards_h + cards_a, 0.5)
    over = sum(_poisson(k, lam) for k in range(int(line) + 1, 20))
    out = {"exp_cards": round(lam, 1), "over": round(over, 4),
           "under": round(1 - over, 4), "line": line,
           "home": round(cards_h, 1), "away": round(cards_a, 1)}
    # Over/Under multi-lignes (module Cartons autonome)
    lines = {}
    for ln in (2.5, 3.5, 4.5):
        o = sum(_poisson(k, lam) for k in range(int(ln) + 1, 20))
        lines[str(ln)] = {"over": round(o, 4), "under": round(1 - o, 4)}
    out["lines"] = lines
    # Probabilité d'au moins 1 carton rouge :
    # historiquement ~22-25% des matchs de CDM voient ≥1 rouge ; sans stat fiable
    # par équipe, on dérive une borne conservatrice à partir du volume de cartons
    # attendu (plus de cartons -> plus de risque), bornée [0.06, 0.40].
    # C'est une APPROXIMATION STRUCTURELLE, étiquetée comme telle dans l'UI.
    p_red = max(0.06, min(0.40, 0.05 * lam))
    out["redProb"] = round(p_red, 3)
    if fouls_h is not None:
        out["foulsHome"] = round(fouls_h, 1)
    if fouls_a is not None:
        out["foulsAway"] = round(fouls_a, 1)
    return out

