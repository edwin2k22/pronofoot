"""
Point 5 — Pondération progressive (shrinkage Bayésien).

Empêche l'overreaction quand on a peu de données : une moyenne d'équipe est tirée
vers un PRIOR (la moyenne du tournoi) tant qu'elle a joué peu de matchs.

    valeur_estimée = (n * observé + k * prior) / (n + k)

n = nb d'observations, k = "force" du prior (en nb de matchs équivalents).
Plus n grand -> on fait confiance aux données ; n petit -> on reste près du prior.
"""
from __future__ import annotations


def shrink(observed_mean: float, n: int, prior: float, k: float = 4.0) -> float:
    """Moyenne post-shrinkage. k=4 -> il faut ~4 matchs pour peser autant que le prior."""
    if n <= 0:
        return prior
    return (n * observed_mean + k * prior) / (n + k)


def update_running_mean(old_mean: float, old_n: int, new_value: float) -> tuple[float, int]:
    """Mise à jour incrémentale d'une moyenne (évite de tout recharger)."""
    new_n = old_n + 1
    new_mean = old_mean + (new_value - old_mean) / new_n
    return round(new_mean, 3), new_n
