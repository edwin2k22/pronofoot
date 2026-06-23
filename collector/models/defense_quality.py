"""
Qualité défensive d'une équipe, basée sur les notes EA FC et statistiques défensives.
Permet d'appliquer un "bouclier" (réduction de λ adverse) si l'équipe a des défenseurs d'élite.
"""
from __future__ import annotations

_DEF = ("DF", "CB", "RB", "LB", "GK")

def _is_def(poste):
    p = str(poste or "").upper().split("/")[0]
    return any(p.startswith(k) for k in _DEF)

def defense_rating(roster):
    """
    Renvoie {stars, shield, names} pour une équipe.
    Évalue la qualité défensive en comptant les traits EA FC / Statistiques des défenseurs.
    """
    if not roster:
        return {"stars": 0, "shield": 1.0, "names": []}
        
    names = []
    points = 0.0
    
    for pl in roster:
        if not _is_def(pl.get("poste")):
            continue
            
        nm = pl.get("joueur") or pl.get("name")
        bio = pl.get("bio") or {}
        forces = bio.get("forces", [])
        if isinstance(forces, str):
            forces = [forces]
            
        score = 0.0
        for f in forces:
            f = str(f).lower()
            if "défense > 80" in f or "récupération" in f or "solid player" in f:
                score += 1.0
            if "impact physique" in f or "physique important" in f or "power header" in f:
                score += 0.5
            if "tacles" in f or "interceptions" in f:
                score += 0.5
                
        if score >= 1.0:
            names.append(nm)
            points += score
            
    # Chaque 1.0 point = ~1 "Star" défensive.
    # On borne le bouclier à -15% max (0.85 multiplicateur)
    # Ex: 4 stars = 1.0 - 0.02 * 4 = 0.92
    shield = round(max(0.85, 1.0 - 0.02 * points), 3)
    return {"stars": round(points, 1), "shield": shield, "names": names[:5]}
