"""
Moyennes RÉELLES de corners et cartons par sélection — source : FootyStats
(https://footystats.org/world-cup), sur les 10 derniers matchs internationaux.

⚠️ ZÉRO invention : valeurs relevées sur footystats (juin 2026).
  - corners = corners tirés par l'équipe / match (colonne "Corners")
  - cards   = cartons reçus par l'équipe / match  (colonne "Cards" = total /10 matchs)
Ces vraies moyennes servent de PRIOR PERSONNALISÉ dans le pipeline (au lieu du
prior générique 5.0 / 2.0). Elles seront, comme avant, mélangées par shrinkage
avec les vrais résultats CDM 2026 au fil du tournoi.

Noms = nomenclature de la base (United States, Czech Republic, Turkey, Curaçao…).
"""
from __future__ import annotations

# {équipe : (corners_moyens_par_match, cartons_moyens_par_match)}
SETPIECES = {
    "Germany": (10.4, 1.3),     "Austria": (7.7, 2.0),     "England": (9.8, 0.8),
    "France": (8.5, 1.6),       "Turkey": (11.5, 2.3),     "Argentina": (7.3, 1.8),
    "Spain": (9.4, 0.6),        "Belgium": (11.8, 1.1),    "Portugal": (8.4, 1.6),
    "Japan": (7.6, 1.3),        "Mexico": (7.4, 2.1),      "Algeria": (9.34, 1.9),
    "Senegal": (10.2, 2.3),     "Croatia": (10.9, 1.3),    "Ivory Coast": (9.2, 0.8),
    "Colombia": (7.4, 0.7),     "Norway": (8.2, 0.6),      "Netherlands": (8.9, 0.8),
    "Morocco": (8.77, 1.3),     "DR Congo": (7.75, 0.6),   "Scotland": (10.9, 1.5),
    "South Korea": (8.4, 1.4),  "Brazil": (7.3, 1.3),      "United States": (10.0, 1.5),
    "Cape Verde": (8.89, 1.5),  "Ecuador": (8.1, 2.1),     "Egypt": (8.5, 1.8),
    "Switzerland": (8.6, 0.6),  "Jordan": (9.9, 1.0),      "Iraq": (9.3, 1.8),
    "Uzbekistan": (8.6, 0.7),   "Czech Republic": (8.89, 0.8), "Australia": (6.5, 1.0),
    "Uruguay": (9.33, 2.0),     "Panama": (8.6, 1.6),      "Iran": (7.88, 0.8),
    "Canada": (9.9, 3.0),       "Haiti": (9.5, 1.8),       "Curaçao": (7.89, 1.1),
    "Paraguay": (7.9, 2.4),     "Bosnia & Herzegovina": (9.3, 2.6), "Tunisia": (10.1, 1.8),
    "South Africa": (7.0, 2.2), "Saudi Arabia": (7.4, 1.4), "Ghana": (8.7, 1.6),
    "Sweden": (9.1, 1.6),       "Qatar": (9.5, 1.3),       "New Zealand": (9.6, 1.0),
}


def get_corners(team):
    v = SETPIECES.get(team)
    return v[0] if v else None


def get_cards(team):
    v = SETPIECES.get(team)
    return v[1] if v else None
