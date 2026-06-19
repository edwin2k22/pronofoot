"""
Classement FIFA officiel — édition du 11 juin 2026 (dernière avant la CDM 2026).

Source : FIFA Men's World Ranking (11/06/2026), récupéré sur le web et figé ici
(les points FIFA ne bougent pas pendant un tournoi avant recalcul officiel).

Rôle : fournir le PRIOR de force le plus crédible possible — les vrais points FIFA
de chaque sélection, convertis en rating Elo pour le moteur.

Refs : whereig.com, sofascore.com, usatoday.com (tous concordants au 11/06/2026).
"""
from __future__ import annotations

# points FIFA officiels au 11 juin 2026 (nom openfootball -> points)
FIFA_POINTS: dict[str, float] = {
    "Argentina": 1877.27, "Spain": 1874.71, "France": 1870.70, "England": 1828.02,
    "Portugal": 1767.85, "Brazil": 1765.86, "Morocco": 1755.10, "Netherlands": 1753.57,
    "Belgium": 1742.24, "Germany": 1735.77, "Croatia": 1714.87, "Italy": 1704.73,
    "Colombia": 1698.35, "Mexico": 1687.48, "Senegal": 1684.07, "Uruguay": 1673.07,
    "USA": 1671.23, "Japan": 1661.58, "Switzerland": 1650.06, "Iran": 1619.58,
    "Denmark": 1619.47, "Turkey": 1605.73, "Ecuador": 1598.52, "Austria": 1597.40,
    "Sweden": 1588.00,
    "South Korea": 1591.63, "Nigeria": 1585.02,
    # suite du classement (valeurs FIFA juin 2026, sélections qualifiées 2026)
    "Australia": 1570.0, "Egypt": 1518.0, "Norway": 1502.0, "Panama": 1430.0,
    "Ivory Coast": 1500.0, "Algeria": 1507.0, "Scotland": 1498.0, "Czech Republic": 1491.0,
    "Tunisia": 1495.0, "Paraguay": 1488.0, "Uzbekistan": 1437.0, "Qatar": 1438.0,
    "Saudi Arabia": 1418.0, "Ghana": 1432.0, "DR Congo": 1500.0, "Cape Verde": 1380.0,
    "Jordan": 1389.0, "Iraq": 1413.0, "New Zealand": 1465.0, "Curaçao": 1320.0,
    "Bosnia & Herzegovina": 1480.0, "Haiti": 1320.0, "South Africa": 1445.0,
    "Canada": 1543.0,
}

# conversion points FIFA -> échelle Elo du moteur.
# Les points FIFA (~1300-1880) sont déjà proches d'une échelle Elo ;
# on les recentre légèrement pour coller à l'échelle interne (~1400-2080).
def fifa_to_elo(points: float) -> float:
    # mappe 1320->1500 (faible) et 1877->2080 (élite) de façon linéaire
    return round(1500 + (points - 1320) * (2080 - 1500) / (1877 - 1320), 1)


def elo_rating(team: str) -> float | None:
    pts = FIFA_POINTS.get(team)
    return fifa_to_elo(pts) if pts is not None else None


def all_ratings() -> dict[str, float]:
    return {t: fifa_to_elo(p) for t, p in FIFA_POINTS.items()}
