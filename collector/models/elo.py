"""
Points 2, 4, 5 — Prior de force + mise à jour Elo avec pondération progressive.

- Prior (point 2) : Elo initialisé depuis le rating FIFA/Elo de team_ratings.
- Update (point 4) : après chaque match réel, on ajuste l'Elo selon le résultat
  ET la qualité de jeu (xG, pas seulement le score → moins de bruit).
- Anti-overreaction (point 5) : K-factor DÉCROISSANT avec le nombre de matchs joués.
  Au début on apprend vite (K élevé), puis on se stabilise (K faible).
"""
from __future__ import annotations
import math

HOME_ADV_ELO = 60          # avantage terrain en points Elo (neutre en CDM ≈ faible)
BASE_K = 40                # K initial (apprentissage rapide)
MIN_K = 12                 # K plancher (stabilité)
XG_BLEND = 0.35            # part du xG dans le "résultat effectif" (vs score brut)


def expected_score(elo_a: float, elo_b: float, home_adv: float = 0.0) -> float:
    """Probabilité Elo que A batte B (0..1)."""
    return 1.0 / (1.0 + 10 ** (-((elo_a + home_adv) - elo_b) / 400.0))


def dynamic_k(matches_played: int) -> float:
    """K décroît avec l'expérience -> évite l'overreaction (point 5)."""
    k = BASE_K / (1.0 + matches_played / 6.0)
    return max(MIN_K, k)


def actual_result(goals_for: int, goals_against: int,
                  xg_for: float | None, xg_against: float | None) -> float:
    """
    Résultat 'effectif' dans [0,1] : mélange score (1/0.5/0) et signal xG.
    Utiliser le xG réduit le bruit (une victoire chanceuse compte moins).
    """
    score_res = 1.0 if goals_for > goals_against else 0.5 if goals_for == goals_against else 0.0
    if xg_for is None or xg_against is None or (xg_for + xg_against) == 0:
        return score_res
    xg_res = xg_for / (xg_for + xg_against)   # part d'xG = "méritait combien"
    return (1 - XG_BLEND) * score_res + XG_BLEND * xg_res


def goal_multiplier(goals_for: int, goals_against: int) -> float:
    """Bonus marge de victoire (large succès -> ajustement un peu plus fort)."""
    diff = abs(goals_for - goals_against)
    if diff <= 1:
        return 1.0
    return 1.0 + math.log(diff) * 0.4    # 2 buts ->1.28, 3 ->1.44, 4 ->1.55


def update_pair(elo_h, elo_a, gh, ga, xgh, xga, played_h, played_a):
    """
    Renvoie (nouvel_elo_home, nouvel_elo_away).
    Applique avantage terrain, K dynamique, marge de victoire et blend xG.
    """
    exp_h = expected_score(elo_h, elo_a, HOME_ADV_ELO)
    res_h = actual_result(gh, ga, xgh, xga)
    mult = goal_multiplier(gh, ga)
    k_h = dynamic_k(played_h) * mult
    k_a = dynamic_k(played_a) * mult
    delta_h = k_h * (res_h - exp_h)
    new_h = elo_h + delta_h
    new_a = elo_a - k_a * (res_h - exp_h)   # jeu à somme nulle
    return round(new_h, 1), round(new_a, 1)
