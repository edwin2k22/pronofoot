"""
Transition Knockout — marché "Qui se qualifie ?" (90' → prolongations → tirs au but).

En élimination directe, le marché 1N2 (temps réglementaire) ne suffit pas : il faut
la proba de QUALIFICATION. On enchaîne :

  1. 90' : grille de scores corrigée (Dixon-Coles) -> P(victoire A), P(nul), P(victoire B)
  2. Prolongations (2×15') : si nul à 90', on rejoue avec λ,μ RÉDUITS de 70%
     (fatigue, chute du xG/minute) mais on garde l'écart Elo.
  3. Tirs au but : si encore nul, la qualif n'est PAS un 50/50 — elle dépend du
     ratio de clean sheets des gardiens et du sang-froid des tireurs (proxy Elo + forme).

Renvoie P(A se qualifie) et P(B se qualifie).
"""
from __future__ import annotations
from . import score_grid as sg

ET_REDUCTION = 0.30        # λ prolongation = 30% de λ (réduction de 70%)


def _win_probs(lam, mu, rho, gamma):
    g = sg.score_grid(lam, mu, rho, gamma)
    o = sg.outcomes(g)
    return o["p1"], o["pX"], o["p2"]


def shootout_prob(elo_h, elo_a, form_h=None, form_a=None) -> float:
    """
    P(équipe domicile gagne la séance de tirs au but).
    Basé sur : écart Elo (qualité gardien/tireurs ~ corrélée au niveau) + forme.
    Borné [0.35, 0.65] : un shootout reste très aléatoire, jamais 50/50 pur mais
    jamais écrasant non plus.
    """
    base = 1.0 / (1.0 + 10 ** (-(elo_h - elo_a) / 600.0))   # Elo -> proba, pente douce
    # bonus de forme (sang-froid récent)
    fh = (form_h or {}).get("form_index", 0.5) if form_h else 0.5
    fa = (form_a or {}).get("form_index", 0.5) if form_a else 0.5
    base += (fh - fa) * 0.08
    return round(min(0.65, max(0.35, base)), 4)


def qualification(lam_h, lam_a, elo_h, elo_a, rho=sg.DEFAULT_RHO, gamma=0.0,
                  form_h=None, form_a=None) -> dict:
    """
    Probabilité de qualification de chaque équipe en match à élimination directe.
    """
    # 1) temps réglementaire
    p1, px, p2 = _win_probs(lam_h, lam_a, rho, gamma)

    # 2) prolongations (sur la part 'nul' à 90'), λ réduits
    lh_et, la_et = lam_h * ET_REDUCTION, lam_a * ET_REDUCTION
    e1, ex, e2 = _win_probs(lh_et, la_et, rho, gamma)

    # 3) tirs au but (sur la part 'nul' après prolongation)
    so_h = shootout_prob(elo_h, elo_a, form_h, form_a)

    # composition : A se qualifie si gagne en 90', OU nul puis gagne en prolong.,
    # OU nul+nul puis gagne aux TAB
    qh = p1 + px * (e1 + ex * so_h)
    qa = p2 + px * (e2 + ex * (1 - so_h))
    # normalisation (sécurité)
    tot = qh + qa
    if tot > 0:
        qh, qa = qh / tot, qa / tot
    return {
        "qualifyHome": round(qh, 4), "qualifyAway": round(qa, 4),
        "reg90": {"p1": p1, "pX": px, "p2": p2},
        "shootoutHome": so_h,
        "note": "90' → prolongations (λ−70%) → tirs au but (Elo+forme)",
    }
