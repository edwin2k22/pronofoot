"""
Impact de la composition sur les probabilités — les 3 angles.

ANGLE 1 (Data) : VORP / Delta de rotation
  - chaque joueur a un sous-rating (hybride : positionnel + Elo équipe, ou vrai xG/xA si dispo)
  - on compare le XI aligné au XI "idéal" de l'effectif -> Delta_rotation
  - λ_ajusté = λ_base × (1 - Delta_rotation_attaque) côté offensif

ANGLE 2 (Tactique) : duel des systèmes + Bench Impact
  - matrice de modificateurs formation vs formation (ex 3-5-2 étouffe 4-3-3 au milieu)
  - Bench Impact Score : qualité des remplaçants (surtout finisseurs) -> bonus Over 2.5 fin de match

ANGLE 3 (UI) : fourni par l'app (mini-terrain) — ici on expose les ratings/forme par joueur.
"""
from __future__ import annotations

# ----- poids de poste pour le rating positionnel (base 1.0) -----
# Reflète l'impact offensif/défensif moyen du poste.
POS_WEIGHT = {
    "GK": 0.85, "DF": 0.92, "CB": 0.92, "RB": 0.95, "LB": 0.95,
    "MF": 1.00, "DM": 0.96, "CM": 1.02, "AM": 1.08,
    "FW": 1.12, "CF": 1.14, "RW": 1.10, "LW": 1.10, "ST": 1.14,
}
# contribution offensive d'un poste (pour le VORP attaque)
POS_OFFENSIVE = {
    "GK": 0.0, "DF": 0.1, "CB": 0.1, "RB": 0.25, "LB": 0.25,
    "MF": 0.5, "DM": 0.3, "CM": 0.55, "AM": 0.8,
    "FW": 1.0, "CF": 1.0, "RW": 0.9, "LW": 0.9, "ST": 1.0,
}

# ----- matrice tactique : modificateur offensif du domicile selon (form_dom vs form_ext) -----
# >1 = avantage offensif domicile ; <1 = étouffé. Plage prudente (±10% max).
# Principe : surnombre au milieu = contrôle ; bloc bas à 5 = étouffe les ailes ;
# 2 attaquants contre 3 défenseurs centraux = neutralisé.
TACTICAL = {
    # 4-3-3 face aux blocs
    ("4-3-3", "5-3-2"): 0.96, ("4-3-3", "5-4-1"): 0.93, ("4-3-3", "3-5-2"): 0.94,
    ("4-3-3", "4-4-2"): 1.04, ("4-3-3", "4-5-1"): 0.97, ("4-3-3", "4-2-3-1"): 1.00,
    ("4-3-3", "3-4-3"): 1.02, ("4-3-3", "4-3-3"): 1.00,
    # 3-5-2 : domine le milieu
    ("3-5-2", "4-3-3"): 1.06, ("3-5-2", "4-4-2"): 1.05, ("3-5-2", "3-5-2"): 1.00,
    ("3-5-2", "4-2-3-1"): 1.03, ("3-5-2", "5-3-2"): 0.98,
    # 4-2-3-1 : équilibré, fort en transition
    ("4-2-3-1", "4-3-3"): 1.00, ("4-2-3-1", "4-4-2"): 1.03, ("4-2-3-1", "5-3-2"): 0.97,
    ("4-2-3-1", "3-5-2"): 0.98, ("4-2-3-1", "4-2-3-1"): 1.00,
    # 4-4-2 : classique, vulnérable au surnombre central
    ("4-4-2", "4-3-3"): 0.97, ("4-4-2", "3-5-2"): 0.95, ("4-4-2", "4-2-3-1"): 0.98,
    ("4-4-2", "4-4-2"): 1.00, ("4-4-2", "5-3-2"): 0.97,
    # 3-4-3 : offensif mais exposé
    ("3-4-3", "3-4-2-1"): 1.02, ("3-4-3", "4-3-3"): 1.01, ("3-4-3", "5-4-1"): 0.95,
    ("3-4-3", "4-4-2"): 1.05, ("3-4-3", "3-4-3"): 1.00,
    # 3-4-2-1
    ("3-4-2-1", "3-4-3"): 0.98, ("3-4-2-1", "4-3-3"): 1.00, ("3-4-2-1", "4-4-2"): 1.03,
    # blocs bas (peu offensifs par nature)
    ("5-3-2", "4-3-3"): 0.95, ("5-4-1", "4-3-3"): 0.90, ("5-4-1", "4-4-2"): 0.93,
    ("4-5-1", "4-3-3"): 0.94,
}


def _norm_pos(pos: str) -> str:
    p = (pos or "").upper().strip()
    if p in POS_WEIGHT:
        return p
    if p.startswith("G"): return "GK"
    if p.startswith("D"): return "DF"
    if p.startswith("M"): return "MF"
    if p.startswith("F") or p.startswith("S") or p.startswith("A") or p.startswith("W"): return "FW"
    return "MF"


def player_rating(pos: str, team_elo: float, real_xg: float | None = None,
                  real_xa: float | None = None) -> float:
    """
    Sous-rating joueur (échelle ~ team_elo). Hybride :
    - base = team_elo × poids_de_poste
    - si vrai xG/xA dispo, on les mélange (bascule progressive vers le réel).
    """
    base = team_elo * POS_WEIGHT.get(_norm_pos(pos), 1.0)
    if real_xg is None and real_xa is None:
        return round(base, 1)
    # contribution réelle (xG+xA par match) ramenée sur l'échelle Elo
    real_pts = (real_xg or 0) + (real_xa or 0)        # ~0..1.5
    real_component = team_elo * (0.9 + real_pts * 0.25)
    return round(0.5 * base + 0.5 * real_component, 1)


def rotation_delta(xi_positions, team_elo, ideal_offensive_avg=None,
                   ideal_defensive_avg=None, real_stats=None):
    """
    ANGLE 1 — compare la force OFFENSIVE et DEFENSIVE du XI aligné à un XI 'idéal'.
    Renvoie (offense_delta, defense_delta).
    >0 = équipe affaiblie (remplaçants alignés).
    """
    if not xi_positions:
        return 0.0, 0.0

    offense = 0.0
    defense = 0.0
    for i, pos in enumerate(xi_positions):
        rs = (real_stats or {}).get(i, {})
        r = player_rating(pos, team_elo, rs.get("xg"), rs.get("xa"))
        norm_p = _norm_pos(pos)
        
        # Offense: FW, AM, RW, LW contribuent le plus
        offense += r * POS_OFFENSIVE.get(norm_p, 0.5)
        
        # Defense: GK, CB, DF, DM contribuent le plus
        def_weight = 1.0 if norm_p in ["GK", "CB"] else (0.8 if norm_p in ["DF", "RB", "LB", "DM"] else 0.2)
        defense += r * def_weight

    avg_off = offense / len(xi_positions)
    avg_def = defense / len(xi_positions)
    
    # références idéales approximatives (11 type)
    ref_off = ideal_offensive_avg or (team_elo * 0.55)
    ref_def = ideal_defensive_avg or (team_elo * 0.45)
    
    d_off = (ref_off - avg_off) / ref_off
    d_def = (ref_def - avg_def) / ref_def
    
    return max(0.0, min(0.20, d_off)), max(0.0, min(0.20, d_def))


def tactical_modifier(home_formation: str, away_formation: str) -> float:
    """ANGLE 2 — modificateur offensif domicile selon le duel de systèmes."""
    return TACTICAL.get((home_formation or "", away_formation or ""), 1.0)


def bench_impact(bench_positions, team_elo) -> float:
    """
    ANGLE 2 — Bench Impact Score [0..1] : qualité offensive du banc (surtout finisseurs).
    Sert de bonus pour l'Over 2.5 en fin de match (5 changements possibles).
    """
    if not bench_positions:
        return 0.0
    fwd = sum(1 for p in bench_positions if _norm_pos(p) == "FW")
    quality = sum(POS_OFFENSIVE.get(_norm_pos(p), 0.4) for p in bench_positions)
    score = (quality / max(len(bench_positions), 1)) * (1 + 0.15 * min(fwd, 3))
    return round(min(1.0, score), 2)


def formation_positions(formation: str) -> list[str]:
    """
    '4-3-3' -> ['GK','DF','DF','DF','DF','MF','MF','MF','FW','FW','FW'].
    Permet d'évaluer une compo à partir de sa seule formation (utile à venir & passé).
    """
    if not formation:
        return ["GK"] + ["DF"]*4 + ["MF"]*3 + ["FW"]*3   # 4-3-3 par défaut
    parts = []
    for n in formation.split("-"):
        try:
            parts.append(int(n))
        except ValueError:
            pass
    if not parts:
        return ["GK"] + ["DF"]*4 + ["MF"]*3 + ["FW"]*3
    lines = ["GK"]
    # 1ère ligne = DF, dernière = FW, intermédiaires = MF
    for i, n in enumerate(parts):
        if i == 0:
            lines += ["DF"] * n
        elif i == len(parts) - 1:
            lines += ["FW"] * n
        else:
            lines += ["MF"] * n
    return lines


def apply_lineup(lam_home, lam_away, home_xi_pos, away_xi_pos,
                 home_form, away_form, home_bench=None, away_bench=None,
                 home_elo=1700, away_elo=1700, real_home=None, real_away=None):
    """
    Combine les 3 leviers et renvoie (lam_home_ajusté, lam_away_ajusté, infos).
    """
    dh_off, dh_def = rotation_delta(home_xi_pos, home_elo, real_stats=real_home)
    da_off, da_def = rotation_delta(away_xi_pos, away_elo, real_stats=real_away)
    tac = tactical_modifier(home_form, away_form)

    # L'équipe Home marque selon sa force offensive (baisse si dh_off > 0)
    # et encaisse selon sa faiblesse défensive (adversaire marque + si dh_def > 0)
    lh = lam_home * (1 - dh_off) * (1 + da_def) * tac
    la = lam_away * (1 - da_off) * (1 + dh_def) * (2 - tac)   # effet miroir tactique côté extérieur

    bh = bench_impact(home_bench, home_elo)
    ba = bench_impact(away_bench, away_elo)

    return round(max(0.2, lh), 2), round(max(0.2, la), 2), {
        "rotationDeltaHome": round(dh_off, 3), "rotationDeltaAway": round(da_off, 3),
        "defensiveDeltaHome": round(dh_def, 3), "defensiveDeltaAway": round(da_def, 3),
        "missingKeyPlayers": [], # sera rempli par la pipeline si des stars manquent
        "tacticalMod": round(tac, 3),
        "benchHome": bh, "benchAway": ba,
        "benchBonusOver25": round((bh + ba) / 2 * 0.06, 3),  # jusqu'à +6% Over 2.5
    }
