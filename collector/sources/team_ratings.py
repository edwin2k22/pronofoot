"""
Table de ratings des 48 sélections de la CDM 2026 (base FIFA / Elo, mi-2026).

Pourquoi : les équipes nationales n'ont pas de "moyenne de buts de championnat".
On approxime leur force par un rating (~ échelle Elo) puis on le convertit en
"buts attendus" pour alimenter le moteur Poisson (couche 2).

⚠️ Ces ratings sont une ESTIMATION de départ, à affiner. Ils ne remplacent pas
le vrai xG. Ils servent de prior raisonnable tant qu'on n'a pas les stats du tournoi.
Au fil des matchs joués, on peut les mettre à jour avec les résultats réels.

Échelle : ~1400 (faible) → ~2100 (élite). Moyenne mondiale ~1600.
"""
from __future__ import annotations

# rating approximatif (Elo-like) — top nations vers 2026
RATINGS: dict[str, int] = {
    # Élite
    "Argentina": 2070, "France": 2060, "Spain": 2050, "England": 2010,
    "Brazil": 2000, "Portugal": 1980, "Netherlands": 1970, "Germany": 1960,
    "Belgium": 1930, "Croatia": 1910, "Italy": 1910, "Uruguay": 1900,
    # Très solides
    "Colombia": 1880, "Morocco": 1875, "Switzerland": 1860, "USA": 1850,
    "Mexico": 1845, "Japan": 1840, "Senegal": 1835, "Denmark": 1830,
    "Ecuador": 1810, "Austria": 1805, "Sweden": 1800, "Iran": 1795,
    # Milieu de tableau
    "Korea Republic": 1785, "South Korea": 1785, "Australia": 1780,
    "Ukraine": 1775, "Norway": 1775, "Canada": 1770, "Egypt": 1765,
    "Nigeria": 1760, "Serbia": 1758, "Turkey": 1755, "Poland": 1750,
    "Ivory Coast": 1745, "Algeria": 1740, "Scotland": 1735, "Czech Republic": 1730,
    "Tunisia": 1715, "Paraguay": 1710, "Uzbekistan": 1700, "Qatar": 1695,
    "Saudi Arabia": 1690, "Ghana": 1685, "DR Congo": 1680, "Cape Verde": 1640,
    # Outsiders
    "Panama": 1620, "Jordan": 1615, "Iraq": 1610, "New Zealand": 1600,
    "Curaçao": 1560, "Bosnia & Herzegovina": 1700, "Haiti": 1545,
    "South Africa": 1640,
}

DEFAULT_RATING = 1620
LEAGUE_AVG_GOALS = 1.35   # buts/match moyen de référence


def get_rating(team: str) -> int:
    # priorité au VRAI classement FIFA juin 2026 (prior le plus crédible)
    try:
        from .fifa_ranking import elo_rating
        fifa = elo_rating(team)
        if fifa is not None:
            return int(round(fifa))
    except Exception:
        pass
    return RATINGS.get(team, DEFAULT_RATING)
