"""
Qualité offensive individuelle d'une équipe.

Problème repéré (analyse France-Sénégal) : le modèle se fie à l'Elo collectif et
au prior générique, donc il sous-estime une équipe au front offensif d'élite mais
sans match CDM encore joué (ex. Sénégal avec Mané/Jackson/Sarr).

Solution : compter les attaquants/ailiers/meneurs RECONNUS (présents dans
player_bios = profil réel documenté) et en déduire un léger bonus de λ offensif,
borné pour rester prudent (on ne transforme pas un outsider en favori).

100% basé sur des données réelles (effectif + bios sourcées). Aucune invention.
"""
from __future__ import annotations
from collector.sources import player_bios as bios

# postes considérés comme offensifs
_OFF = ("FW", "AC", "BU", "ATT", "AG", "AD", "AILIER", "MO", "AM")


def _is_off(poste):
    p = str(poste or "").upper().split("/")[0]
    return any(p.startswith(k) for k in _OFF)


def attack_rating(roster):
    """
    Renvoie {stars, boost, names} pour une équipe.
    stars  = nb d'attaquants/créateurs avec une bio réelle (= qualité reconnue)
    boost  = multiplicateur de λ offensif, borné [1.0, 1.18]
             (+~4% par star offensive, max +18%)
    """
    if not roster:
        return {"stars": 0, "boost": 1.0, "names": []}
    names = []
    for pl in roster:
        nm = pl.get("joueur") or pl.get("name")
        if not nm:
            continue
        b = bios.get_bio(nm)
        if b and _is_off(pl.get("poste") or b.get("role")):
            names.append(nm)
    stars = len(names)
    boost = round(min(1.18, 1.0 + 0.04 * stars), 3)
    return {"stars": stars, "boost": boost, "names": names[:5]}
