"""
Intelligence contextuelle — 3 angles avancés au-dessus du calcul brut.

ANGLE 1 (Théorie des jeux) : Must-Win Index (MWI)
  L'enjeu modifie le comportement. Une équipe qui DOIT gagner attaque plus ;
  une équipe déjà qualifiée lève le pied (rotation, baisse d'intensité).
  -> multiplicateur d'urgence sur λ_attaque, malus d'intensité défensive adverse.

ANGLE 2 (Métacognition) : Indice de Confiance du Modèle
  Le modèle s'auto-évalue : données récentes ? volatilité de la forme ? historique
  suffisant ? -> confiance ∈ [0,1]. Sert à fractionner le Kelly (mise prudente).

ANGLE 3 (Risque quantitatif) : Line Movement / Trap Game
  Compare la prédiction au mouvement de cote (ouverture -> actuelle). Si l'app voit
  de la value mais que le marché va agressivement dans l'autre sens -> alerte "piège".
"""
from __future__ import annotations


# ---------------- ANGLE 1 : Must-Win Index ----------------
# stade -> enjeu de base (3e match de poule = enjeu max ; phase finale = élimination directe)
STAGE_STAKES = {
    "Matchday 1": 0.3, "Matchday 2": 0.5, "Matchday 3": 0.9,
    "Round of 32": 1.0, "Round of 16": 1.0, "Quarter-final": 1.0,
    "Semi-final": 1.0, "Final": 1.0, "Match for third place": 0.4,
}


def must_win_index(stage: str, qualified_home: bool | None = None,
                   qualified_away: bool | None = None) -> dict:
    """
    Calcule l'urgence de chaque équipe (0..1) selon le stade et l'état de qualification.
    qualified_* : True = déjà qualifié (lève le pied), False = doit gagner, None = inconnu.
    """
    base = 0.5
    for key, v in STAGE_STAKES.items():
        if key.lower() in (stage or "").lower():
            base = v
            break
    # en knockout, tout le monde "doit gagner"
    mwi_home = base if qualified_home is None else (0.2 if qualified_home else min(1.0, base + 0.3))
    mwi_away = base if qualified_away is None else (0.2 if qualified_away else min(1.0, base + 0.3))
    return {"home": round(mwi_home, 2), "away": round(mwi_away, 2), "stageStake": base}


def apply_mwi(lam_home, lam_away, mwi):
    """
    Module λ selon l'urgence : une équipe motivée attaque +, une démotivée subit -.
    Effet borné (±12%) pour rester prudent.
    """
    # écart d'urgence : si home plus motivé que away, home attaque mieux et away défend moins
    diff = mwi["home"] - mwi["away"]
    lh = lam_home * (1 + 0.12 * diff)
    la = lam_away * (1 - 0.12 * diff)
    return round(max(0.2, lh), 2), round(max(0.2, la), 2)


# ---------------- ANGLE 2 : Confiance du modèle (métacognition) ----------------
def model_confidence(home_form, away_form, matches_played_home, matches_played_away,
                     form_real_home=True, form_real_away=True) -> dict:
    """
    Auto-évaluation de la fiabilité de la prédiction (0..1).
    Pénalise : peu de données réelles, forme volatile, sources estimées.
    """
    reasons = []
    conf = 1.0

    # 1) données réelles de forme ?
    if not form_real_home or not form_real_away:
        conf -= 0.25; reasons.append("forme estimée (non réelle)")

    # 2) volatilité de la forme : une forme en dents de scie = moins prévisible
    def volatility(f):
        if not f or not f.get("last5"):
            return 0.5
        s = f["last5"]
        # nombre de changements de résultat (W<->L<->D) = instabilité
        changes = sum(1 for i in range(1, len(s)) if s[i] != s[i-1])
        return changes / max(len(s) - 1, 1)
    vol = (volatility(home_form) + volatility(away_form)) / 2
    if vol > 0.6:
        conf -= 0.15; reasons.append("forme volatile (résultats en dents de scie)")

    # 3) peu de matchs CDM joués = on s'appuie surtout sur le prior
    cdm = matches_played_home + matches_played_away
    if cdm == 0:
        conf -= 0.10; reasons.append("aucun match CDM 2026 joué (prior dominant)")

    conf = max(0.3, min(1.0, conf))
    label = "élevée" if conf >= 0.8 else "moyenne" if conf >= 0.55 else "faible"
    return {"confidence": round(conf, 2), "label": label,
            "reasons": reasons or ["données récentes et cohérentes"]}


def kelly_fraction(prob, odds, confidence, cap=0.05) -> dict:
    """
    Critère de Kelly FRACTIONNÉ par la confiance.
      f* = (b·p − q)/b × confiance   (b = cote−1 ; q = 1−p)
    Plafonné (cap) pour la prudence. Renvoie 0 si pas de value.
    """
    if not odds or odds <= 1:
        return {"kelly": 0.0, "note": "cote absente"}
    b = odds - 1
    q = 1 - prob
    raw = (b * prob - q) / b
    if raw <= 0:
        return {"kelly": 0.0, "note": "pas de value (EV ≤ 0)"}
    f = raw * confidence
    f = min(f, cap)               # ne jamais miser plus que le cap
    return {"kelly": round(f, 4), "rawKelly": round(raw, 4),
            "note": f"miser ~{f*100:.1f}% de la bankroll (Kelly×confiance, plafonné {cap*100:.0f}%)"}


# ---------------- ANGLE 3 : Line Movement / Trap Game ----------------
def line_movement(model_prob, opening_odds, current_odds) -> dict | None:
    """
    Compare la prédiction au mouvement de cote (ouverture -> actuelle).
    - si la cote BAISSE, le marché charge cette issue (smart money dessus).
    - si l'app voit de la value sur une issue MAIS que sa cote MONTE
      (marché s'en détourne) -> alerte 'Trap Game'.
    opening_odds / current_odds : cotes de la MÊME issue (ex: victoire domicile).
    Renvoie None si cotes absentes.
    """
    if not opening_odds or not current_odds:
        return None
    drift = round(current_odds - opening_odds, 2)
    pct = round((current_odds - opening_odds) / opening_odds * 100, 1)
    fair = 1 / model_prob if model_prob > 0 else None
    value = fair and current_odds > fair        # value = cote book > cote juste

    if drift < -0.08 * opening_odds:
        market = "smart money SUR cette issue (cote en forte baisse)"
    elif drift > 0.08 * opening_odds:
        market = "marché se détourne (cote en hausse)"
    else:
        market = "cote stable"

    trap = bool(value and drift > 0.08 * opening_odds)   # value mais marché fuit
    return {
        "opening": opening_odds, "current": current_odds,
        "drift": drift, "driftPct": pct,
        "market": market,
        "trapGame": trap,
        "alert": ("⚠️ Trap Game potentiel : value détectée mais l'argent fuit cette issue "
                  "(blessure/info de dernière minute ?)") if trap else None,
    }
