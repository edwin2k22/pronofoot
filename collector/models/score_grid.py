"""
Grille de scores corrigée — Dixon-Coles + Poisson bivarié (effet de choc).

Remplace le Poisson NAÏF (qui suppose l'indépendance des scores des 2 équipes).

1) Dixon-Coles (1997) : corrige la sous-estimation des scores serrés (0-0, 1-0, 0-1,
   1-1) via un paramètre rho (ρ). Améliore le marché "nul" et "Under 1.5".

2) Poisson bivarié (effet de choc) : une variable latente Z3 ~ Poisson(gamma) modélise
   les événements macro affectant les deux équipes (carton rouge précoce, penalty,
   arbitrage, pelouse...). Buts A ~ Poisson(λ+γ), Buts B ~ Poisson(μ+γ).
   γ>0 sur les matchs "à haut risque" gonfle les scénarios extrêmes.

La grille corrigée est ensuite consommée par markets.py (1N2, O/U, BTTS, score exact).
"""
from __future__ import annotations
from math import exp, factorial

MAXG = 8
DEFAULT_RHO = -0.06       # corrélation clean-sheets (Dixon-Coles : entre -0.05 et -0.10)


def _pois(k: int, lam: float) -> float:
    return exp(-lam) * lam ** k / factorial(k)


def _tau(i: int, j: int, lam: float, mu: float, rho: float) -> float:
    """Facteur de correction Dixon-Coles pour les 4 scores critiques."""
    if i == 0 and j == 0:
        return 1.0 - lam * mu * rho
    if i == 1 and j == 0:
        return 1.0 + mu * rho
    if i == 0 and j == 1:
        return 1.0 + lam * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def _bivariate_pmf(i: int, j: int, lam: float, mu: float, gamma: float) -> float:
    """
    Poisson bivarié : P(X=i, Y=j) avec composante commune Z3~Poisson(gamma).
    X = Z1 + Z3, Y = Z2 + Z3 où Z1~P(λ), Z2~P(μ), Z3~P(γ).
    Si gamma=0, se réduit au produit de deux Poisson indépendants.
    """
    if gamma <= 0:
        return _pois(i, lam) * _pois(j, mu)
    total = 0.0
    for k in range(0, min(i, j) + 1):
        total += (_pois(i - k, lam) * _pois(j - k, mu) * _pois(k, gamma))
    return total


def score_grid(lam: float, mu: float, rho: float = DEFAULT_RHO,
               gamma: float = 0.0) -> list[list[float]]:
    """
    Renvoie la grille [i][j] des probabilités de score corrigées (normalisée).
    - rho : correction Dixon-Coles (scores serrés)
    - gamma : effet de choc (corrélation match, gonfle les extrêmes)
    """
    grid = [[0.0] * (MAXG + 1) for _ in range(MAXG + 1)]
    tot = 0.0
    for i in range(MAXG + 1):
        for j in range(MAXG + 1):
            p = _bivariate_pmf(i, j, lam, mu, gamma) * _tau(i, j, lam, mu, rho)
            p = max(p, 0.0)               # tau peut rendre une case légèrement négative
            grid[i][j] = p
            tot += p
    if tot > 0:
        for i in range(MAXG + 1):
            for j in range(MAXG + 1):
                grid[i][j] /= tot
    return grid


def shock_gamma(elo_diff: float, stage_stake: float, high_risk: bool = False) -> float:
    """
    Estime l'effet de choc γ selon le contexte :
    - gros enjeu (J3, knockout) = plus de tension -> γ plus élevé
    - match très serré (faible écart Elo) = plus volatil
    - high_risk : flag manuel (derby, conditions extrêmes)
    γ reste modéré (0..0.15) pour ne pas dénaturer le modèle.
    """
    g = 0.0
    if stage_stake >= 0.8:
        g += 0.05
    if abs(elo_diff) < 60:        # match équilibré = plus d'aléa
        g += 0.04
    if high_risk:
        g += 0.05
    return round(min(g, 0.15), 3)


# ---------- agrégations depuis la grille corrigée ----------
def outcomes(grid) -> dict:
    p1 = px = p2 = over25 = btts = under15 = 0.0
    best = (0, 0, 0.0)
    for i in range(len(grid)):
        for j in range(len(grid[i])):
            p = grid[i][j]
            if i > j: p1 += p
            elif i == j: px += p
            else: p2 += p
            if i + j > 2.5: over25 += p
            if i + j < 1.5: under15 += p
            if i > 0 and j > 0: btts += p
            if p > best[2]: best = (i, j, p)
    return {"p1": round(p1, 4), "pX": round(px, 4), "p2": round(p2, 4),
            "over25": round(over25, 4), "under25": round(1 - over25, 4),
            "under15": round(under15, 4), "btts": round(btts, 4),
            "top_score": (best[0], best[1])}


# ---------- marchés dérivés (Double Chance, Draw No Bet, top-N scores) ----------
def _all_scores(grid):
    """Liste [(i, j, p)] triée par probabilité décroissante."""
    cells = []
    for i in range(len(grid)):
        for j in range(len(grid[i])):
            cells.append((i, j, grid[i][j]))
    cells.sort(key=lambda c: c[2], reverse=True)
    return cells


def derived_markets(grid) -> dict:
    """
    Marchés 100% dérivés de la grille corrigée (aucune donnée externe) :
    - Double Chance : 1X, 12, X2
    - Draw No Bet   : DNB1, DNB2 (nul retiré, renormalisé sur p1+p2)
    - top-3 scores exacts (avec probabilité)
    """
    o = outcomes(grid)
    p1, px, p2 = o["p1"], o["pX"], o["p2"]
    denom = max(p1 + p2, 1e-9)
    cells = _all_scores(grid)
    top3 = [{"score": f"{i}-{j}", "p": round(p, 4)} for (i, j, p) in cells[:3]]
    return {
        "doubleChance": {
            "1X": round(p1 + px, 4),
            "12": round(p1 + p2, 4),
            "X2": round(px + p2, 4),
        },
        "drawNoBet": {
            "home": round(p1 / denom, 4),
            "away": round(p2 / denom, 4),
        },
        "topScores": top3,
    }


# ---------- scénarios narratifs (catégories de score, 100% issus de la grille) ----------
def scenarios(grid) -> list:
    """
    4 scénarios mutuellement exclusifs et exhaustifs, dérivés UNIQUEMENT de la
    grille de scores réelle (aucun timing, aucun historique inventé) :

      1. Match fermé   : total de buts <= 1   (0-0, 1-0, 0-1)
      2. Match serré   : total de buts == 2   (1-1, 2-0, 0-2)
      3. Match spectacle : total de buts >= 3 (Over 2.5 favorisé)
      4. Large écart   : écart >= 2 buts ET total >= 3 (domination nette)

    NB : "Large écart" est un SOUS-ENSEMBLE de "spectacle" ; pour garder une
    partition propre (somme = 100 %), on calcule d'abord les 3 catégories par
    total de buts, puis on expose "large écart" comme un ANGLE supplémentaire
    (non additionné), clairement étiqueté.
    """
    buckets = {
        "closed": {"p": 0.0, "scores": []},   # total <= 1
        "tight":  {"p": 0.0, "scores": []},   # total == 2
        "open":   {"p": 0.0, "scores": []},   # total >= 3
    }
    blowout_p = 0.0
    blowout_scores = []
    for i in range(len(grid)):
        for j in range(len(grid[i])):
            p = grid[i][j]
            tot = i + j
            if tot <= 1:
                key = "closed"
            elif tot == 2:
                key = "tight"
            else:
                key = "open"
            buckets[key]["p"] += p
            buckets[key]["scores"].append((i, j, p))
            if abs(i - j) >= 2 and tot >= 3:
                blowout_p += p
                blowout_scores.append((i, j, p))

    def top_scores(scores, n=2):
        scores = sorted(scores, key=lambda c: c[2], reverse=True)[:n]
        return [f"{i}-{j}" for (i, j, _) in scores]

    out = [
        {
            "id": "closed",
            "title": "Match fermé",
            "p": round(buckets["closed"]["p"], 4),
            "scores": top_scores(buckets["closed"]["scores"]),
            "note": "Peu d'occasions concrétisées · Under 1.5 favorisé",
        },
        {
            "id": "tight",
            "title": "Match serré",
            "p": round(buckets["tight"]["p"], 4),
            "scores": top_scores(buckets["tight"]["scores"]),
            "note": "Décidé par un détail · Under 2.5 proche du pile ou face",
        },
        {
            "id": "open",
            "title": "Match ouvert / spectacle",
            "p": round(buckets["open"]["p"], 4),
            "scores": top_scores(buckets["open"]["scores"]),
            "note": "Over 2.5 favorisé · les deux blocs prennent des risques",
        },
        {
            "id": "blowout",
            "title": "Large écart",
            "p": round(blowout_p, 4),
            "scores": top_scores(blowout_scores),
            "note": "Domination nette d'une équipe (écart ≥ 2 buts) · ANGLE, inclus dans « spectacle »",
            "angle": True,
        },
    ]
    return out


# ---------- Over/Under multi-lignes (dérivés de la grille) ----------
def over_under_lines(grid, lines=(0.5, 1.5, 2.5, 3.5)) -> dict:
    """P(total > ligne) pour plusieurs lignes, calculé sur la grille corrigée."""
    out = {}
    for ln in lines:
        over = 0.0
        for i in range(len(grid)):
            for j in range(len(grid[i])):
                if i + j > ln:
                    over += grid[i][j]
        out[str(ln)] = {"over": round(over, 4), "under": round(1 - over, 4)}
    return out


# ---------- Score à la mi-temps (ratio structurel CDM) ----------
# Part des buts marqués en 1ère mi-temps en Coupe du Monde :
#   - CDM 2022 : 38,9 %  (Art336, efsupit 2023)
#   - 19 CDM 1930-2010 : 43,1 %  (Leite 2013, via ResearchGate)
#   - CDM 2018/2022 : ~40 % (Frontiers 2024)
# Valeur retenue : 0.42 (moyenne robuste). C'est une CONSTANTE STRUCTURELLE du
# football mondial, PAS une stat par équipe — affichée comme telle dans l'UI.
HT_GOAL_SHARE = 0.42


def halftime(lam_h, lam_a, rho=DEFAULT_RHO, gamma=0.0, share=HT_GOAL_SHARE) -> dict:
    """
    Score probable à la mi-temps + O/U mi-temps, en appliquant la même mécanique
    Dixon-Coles aux lambdas de 1ère période (λ × part structurelle des buts en 1ère MT).
    """
    lh = max(lam_h * share, 1e-6)
    la = max(lam_a * share, 1e-6)
    g = score_grid(lh, la, rho=rho, gamma=gamma)
    o = outcomes(g)
    ou = over_under_lines(g, lines=(0.5, 1.5))
    return {
        "lamHome": round(lh, 2),
        "lamAway": round(la, 2),
        "topScore": list(o["top_score"]),
        "p1": o["p1"], "pX": o["pX"], "p2": o["p2"],
        "ou05": ou["0.5"], "ou15": ou["1.5"],
        "share": share,
        "note": "1ère MT estimée via la part structurelle des buts en CDM (~42 %, sources : CDM 2018/2022/2022 & 19 CDM 1930-2010). Pas une stat par équipe.",
    }
