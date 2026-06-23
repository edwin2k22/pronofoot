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

# postes considérés comme offensifs
_OFF = ("FW", "AC", "BU", "ATT", "AG", "AD", "AILIER", "MO", "AM")


def _is_off(poste):
    p = str(poste or "").upper().split("/")[0]
    return any(p.startswith(k) for k in _OFF)


def attack_rating(roster):
    """
    Renvoie {stars, boost, names} pour une équipe.
    Évalue la qualité offensive en comptant les traits EA FC / Statistiques des attaquants.
    """
    if not roster:
        return {"stars": 0, "boost": 1.0, "names": []}
        
    names = []
    points = 0.0
    
    for pl in roster:
        if not _is_off(pl.get("poste")):
            continue
            
        nm = pl.get("joueur") or pl.get("name")
        bio = pl.get("bio") or {}
        forces = bio.get("forces", [])
        if isinstance(forces, str):
            forces = [forces]
            
        score = 0.0
        for f in forces:
            f = str(f).lower()
            if "tir > 80" in f or "finition" in f or "finesse shot" in f:
                score += 1.0
            if "vitesse > 80" in f or "rapide" in f or "speed" in f:
                score += 0.5
            if "passe > 80" in f or "créateur" in f or "playmaker" in f:
                score += 0.5
            if "dribble" in f or "percussion" in f:
                score += 0.5
            if "xg élevé" in f or "occasions dangereuses" in f:
                score += 1.0
                
        if score >= 1.0:
            names.append(nm)
            points += score
            
    # Chaque 1.0 point = ~1 "Star" offensive.
    # On borne le bonus à +18% max
    boost = round(min(1.18, 1.0 + 0.03 * points), 3)
    return {"stars": round(points, 1), "boost": boost, "names": names[:5]}
