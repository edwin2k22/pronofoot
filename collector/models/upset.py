"""
Intelligence "au-delà des maths" — pourquoi un favori peut perdre / un outsider accrocher.

Fondé sur des facteurs RÉELS documentés (recherche : thatsagoal, statpair, opensports
sciences journal, medium/xG) et sur NOS données :
  1) FINITION : buts marqués vs xG. La surperformance de finition régresse vers la
     moyenne (la réussite devant le but ne dure pas) ; un favori qui marquait "facile"
     est ramené à la réalité, un outsider clinique est valorisé.
  2) BLOC BAS : un outsider qui encaisse peu d'xG (défense organisée) frustre les favoris.
  3) CONTEXTE : une équipe qui n'a besoin que d'un nul joue fermé (déjà via MWI).
  4) ROUGE : un carton rouge attendu élevé augmente le chaos (déjà via redProb).
  5) SERREMENT : plus le match est serré (probas proches), plus la surprise est possible.

Sortie : un INDICE DE SURPRISE 0-100 + de légers modulateurs de probabilités
(réduction de la domination du favori quand les signaux d'alerte s'accumulent),
bornés pour rester prudents (le favori reste favori, mais un peu moins écrasant).
"""
from __future__ import annotations


def finishing_factor(goals_avg, xg_avg, n_matches):
    """
    Ratio buts/xG d'une équipe, tiré vers 1.0 (régression vers la moyenne).
    >1 = surperforme sa finition (chanceux/clinique), <1 = gâche ses occasions.
    Renvoie un multiplicateur PRUDENT à appliquer au λ (borné 0.85–1.15).
    """
    if not xg_avg or xg_avg <= 0 or n_matches <= 0:
        return 1.0, None
    raw = goals_avg / xg_avg
    k = 4  # shrinkage fort : peu de matchs -> proche de 1.0
    ratio = (n_matches * raw + k * 1.0) / (n_matches + k)
    # on n'applique qu'une fraction (la finition future régresse) : 50% du signal
    mult = 1.0 + 0.5 * (ratio - 1.0)
    return max(0.85, min(1.15, round(mult, 3))), round(raw, 2)


def upset_index(p_fav, p_dog, xg_fav_eff, dog_low_block, fav_overperf,
                red_prob, dog_needs_draw=False):
    """
    Indice 0-100 du risque que le favori ne gagne pas (nul ou défaite).
    Combine des signaux RÉELS :
      - base = proba que le favori NE gagne PAS (1 - p_fav)
      - + bloc bas de l'outsider (défense solide)
      - + favori qui SURperforme son xG (réussite non durable)
      - + risque de carton rouge (chaos)
      - + match serré
      - + outsider qui n'a besoin que d'un nul
    """
    base = (1 - p_fav) * 100
    bonus = 0
    if dog_low_block:        bonus += 8     # outsider défensivement solide
    if fav_overperf:         bonus += 7     # favori chanceux récemment -> régression
    if red_prob and red_prob > 0.22: bonus += 5
    if abs(p_fav - p_dog) < 0.15: bonus += 6  # match serré
    if dog_needs_draw:       bonus += 5
    idx = max(0, min(100, round(base + bonus)))
    if idx >= 55: label = "élevé"
    elif idx >= 35: label = "modéré"
    else: label = "faible"
    return {"index": idx, "label": label}


def context_dampener(upset_idx):
    """
    Petit facteur (0.90–1.0) qui réduit la domination du favori quand l'indice
    de surprise est élevé. Prudent : ne renverse jamais le favori, l'atténue.
    """
    if upset_idx < 45:
        return 1.0
    # entre 45 et 100 -> dampener de 1.0 à 0.90
    return round(1.0 - 0.10 * ((upset_idx - 45) / 55), 3)
