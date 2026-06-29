#!/usr/bin/env python3
"""
NLP Momentum — Analyse textuelle du commentaire ESPN en temps réel.

Ce module est SANS dépendances externes (no spaCy, no transformers).
Il utilise des règles lexicales sur le texte anglais d'ESPN pour extraire
des signaux de dynamique de match (momentum, pression, danger, fatigue…)
et produit un delta λ (ajustement des buts attendus) pour le pipeline Live.

Architecture :
    commentary (list[dict]) → analyse_commentary() → MomentumSignal

MomentumSignal contient :
  - home_momentum / away_momentum  : [-1.0, +1.0] (>0 = équipe domine)
  - home_lambda_adj / away_lambda_adj : multiplicateurs suggérés pour λ Poisson
  - signals (list[str])            : signaux textuels détectés
  - pressure_home / pressure_away  : bool (l'équipe est-elle sous pression ?)
  - dominance                      : "home" | "away" | "balanced"
"""
from __future__ import annotations
import re
from typing import NamedTuple


# ---------------------------------------------------------------------------
#  Dictionnaires de signaux lexicaux
#  Chaque entrée = (pattern regex, score home, score away)
#  score > 0 → favorable à home, < 0 → favorable à away
# ---------------------------------------------------------------------------

# Patterns d'ATTAQUE (tentatives de tir, situations dangereuses)
_ATTACK_PATTERNS: list[tuple[str, float, float]] = [
    # Tirs sauvegardés / tentatives
    (r"\b(attempt|shot|effort)\b.*(home|{home})",      +0.30, 0.0),
    (r"\b(attempt|shot|effort)\b.*(away|{away})",       0.0, +0.30),
    (r"\bsaved\b.*(home|{home})",                       +0.25, 0.0),
    (r"\bsaved\b.*(away|{away})",                        0.0, +0.25),
    (r"\bcorner\b.*(home|{home}|winning the corner)",   +0.15, 0.0),
    (r"\bcorner\b.*(away|{away}|winning the corner)",    0.0, +0.15),
    # Occasions manquées
    (r"\b(just wide|over the bar|hits the post|hits the bar)\b", +0.10, +0.10),
    # Situation de but
    (r"\b(goal|scores|scores!|headed in|taps in|slots)\b.*(home|{home})", +0.50, 0.0),
    (r"\b(goal|scores|scores!|headed in|taps in|slots)\b.*(away|{away})",  0.0, +0.50),
    # VAR / contrôle
    (r"\bvar\b.*\bcheck\b",                              0.0,  0.0),
]

# Patterns de PRESSION / DOMINATION
_PRESSURE_PATTERNS: list[tuple[str, float, float]] = [
    (r"\b(pressure|pressing|high press)\b.*(home|{home})",  +0.20, 0.0),
    (r"\b(pressure|pressing|high press)\b.*(away|{away})",   0.0, +0.20),
    (r"\b(dominating|dominant|control)\b.*(home|{home})",   +0.25, 0.0),
    (r"\b(dominating|dominant|control)\b.*(away|{away})",    0.0, +0.25),
    (r"\b(possession)\b.*(home|{home})",                    +0.10, 0.0),
    (r"\b(possession)\b.*(away|{away})",                     0.0, +0.10),
    # Substitutions offensives (signal d'urgence)
    (r"\b(substitution|comes on|replaces)\b.*(home|{home})", +0.05, 0.0),
    (r"\b(substitution|comes on|replaces)\b.*(away|{away})",  0.0, +0.05),
]

# Patterns DÉFENSIFS / NÉGATIFS (réduit la pression de l'équipe qui défend)
_DEFENSIVE_PATTERNS: list[tuple[str, float, float]] = [
    (r"\b(clearance|blocks|headed clear|goal-line)\b.*(home|{home})",  -0.10, 0.0),
    (r"\b(clearance|blocks|headed clear|goal-line)\b.*(away|{away})",   0.0, -0.10),
    (r"\b(foul|yellow card|red card|booked)\b.*(home|{home})",         -0.08, 0.0),
    (r"\b(foul|yellow card|red card|booked)\b.*(away|{away})",          0.0, -0.08),
    (r"\b(offside)\b.*(home|{home})",                                   -0.05, 0.0),
    (r"\b(offside)\b.*(away|{away})",                                    0.0, -0.05),
]

# Patterns d'URGENCE temporelle (accélère le momentum de l'équipe qui perd)
_URGENCY_KEYWORDS = [
    "presses forward", "pushing", "all out attack", "desperate",
    "must score", "need a goal", "looking for", "hunting for",
    "time running out", "final minutes", "injury time", "stoppage time",
    "added time", "90+",
]


class MomentumSignal(NamedTuple):
    home_momentum: float          # [-1, +1]
    away_momentum: float          # [-1, +1]
    home_lambda_adj: float        # multiplicateur Poisson (ex: 1.15)
    away_lambda_adj: float        # multiplicateur Poisson (ex: 0.92)
    signals: list[str]            # list des signaux détectés (audit)
    pressure_home: bool           # l'équipe à domicile est-elle sous pression ?
    pressure_away: bool
    urgency_detected: bool        # urgence temporelle détectée
    dominance: str                # "home" | "away" | "balanced"


def analyse_commentary(
    commentary: list[dict],
    home: str,
    away: str,
    current_minute: int = 0,
    window_size: int = 15,       # n'analyser que les N derniers commentaires
) -> MomentumSignal:
    """
    Analyse une liste de commentaires ESPN pour en extraire le momentum.

    Args:
        commentary  : liste de dict ESPN  {"sequence": int, "time": {...}, "text": "..."}
        home        : nom de l'équipe à domicile (pour substitution dans les patterns)
        away        : nom de l'équipe visiteuse
        current_minute : minute de jeu actuelle (pour pondérer par urgence)
        window_size : nombre de commentaires récents à analyser (les plus récents d'abord)

    Returns:
        MomentumSignal
    """
    if not commentary:
        return _neutral()

    # Tri par séquence décroissante → commentaires les plus récents en premier
    sorted_comments = sorted(commentary, key=lambda c: c.get("sequence", 0), reverse=True)
    recent = sorted_comments[:window_size]

    # Extraction du texte brut
    texts = []
    for c in recent:
        txt = c.get("text", "") or ""
        texts.append(txt.lower())

    full_text = " ".join(texts)

    home_l = home.lower()
    away_l = away.lower()

    # Construire les patterns avec les noms d'équipe réels
    def _build(patterns):
        return [
            (pat.replace("{home}", re.escape(home_l)).replace("{away}", re.escape(away_l)), sh, sa)
            for pat, sh, sa in patterns
        ]

    all_patterns = (
        _build(_ATTACK_PATTERNS)
        + _build(_PRESSURE_PATTERNS)
        + _build(_DEFENSIVE_PATTERNS)
    )

    home_score = 0.0
    away_score = 0.0
    signals_detected = []

    for pat, sh, sa in all_patterns:
        try:
            if re.search(pat, full_text, re.IGNORECASE):
                home_score += sh
                away_score += sa
                if sh != 0.0 or sa != 0.0:
                    signals_detected.append(f"[h={sh:+.2f}/a={sa:+.2f}] {pat[:60]}")
        except re.error:
            continue

    # Détection d'urgence temporelle
    urgency = any(kw in full_text for kw in _URGENCY_KEYWORDS)
    if urgency and current_minute >= 75:
        # Si l'équipe qui perd cherche le but, on booste son λ
        # (heuristique : si home_score < away_score → home perd probablement → home cherche)
        if home_score < away_score:
            home_score += 0.30
            signals_detected.append("[urgency] home pushing for goal")
        elif away_score < home_score:
            away_score += 0.30
            signals_detected.append("[urgency] away pushing for goal")

    # Normalisation dans [-1, +1]
    home_mom = max(-1.0, min(1.0, home_score))
    away_mom = max(-1.0, min(1.0, away_score))

    # Conversion en multiplicateur λ
    # momentum +1.0 → ×1.30 (30% de buts en plus), -1.0 → ×0.70
    def _to_lambda(mom: float) -> float:
        return round(1.0 + (mom * 0.30), 4)

    home_lam = _to_lambda(home_mom)
    away_lam = _to_lambda(away_mom)

    # Dominance
    diff = home_mom - away_mom
    if abs(diff) < 0.10:
        dominance = "balanced"
    elif diff > 0:
        dominance = "home"
    else:
        dominance = "away"

    return MomentumSignal(
        home_momentum=round(home_mom, 4),
        away_momentum=round(away_mom, 4),
        home_lambda_adj=home_lam,
        away_lambda_adj=away_lam,
        signals=signals_detected,
        pressure_home=home_mom < -0.20,
        pressure_away=away_mom < -0.20,
        urgency_detected=urgency,
        dominance=dominance,
    )


def _neutral() -> MomentumSignal:
    return MomentumSignal(
        home_momentum=0.0, away_momentum=0.0,
        home_lambda_adj=1.0, away_lambda_adj=1.0,
        signals=[], pressure_home=False, pressure_away=False,
        urgency_detected=False, dominance="balanced",
    )


def momentum_to_dict(sig: MomentumSignal) -> dict:
    """Sérialise le signal en dict JSON-compatible pour predictions.json."""
    return {
        "homeMomentum": sig.home_momentum,
        "awayMomentum": sig.away_momentum,
        "homeLambdaAdj": sig.home_lambda_adj,
        "awayLambdaAdj": sig.away_lambda_adj,
        "dominance": sig.dominance,
        "pressureHome": sig.pressure_home,
        "pressureAway": sig.pressure_away,
        "urgencyDetected": sig.urgency_detected,
        "signalsCount": len(sig.signals),
        # Ne pas inclure la liste complète des signaux dans le JSON de prod
        # (trop verbeux) — juste le résumé
    }


# ---------------------------------------------------------------------------
#  Point d'entrée pour test rapide
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Exemple de test avec des commentaires simulés
    sample = [
        {"sequence": 10, "time": {"displayValue": "85'"}, "text": "Attempt saved. Morocco left footed shot from outside the box."},
        {"sequence": 9,  "time": {"displayValue": "83'"}, "text": "Corner, Morocco. Conceded by Haiti."},
        {"sequence": 8,  "time": {"displayValue": "80'"}, "text": "Haiti clearance, headed away."},
        {"sequence": 7,  "time": {"displayValue": "78'"}, "text": "Morocco pressing forward, time running out for Haiti."},
        {"sequence": 6,  "time": {"displayValue": "75'"}, "text": "Substitution, Morocco. Soufiane Rahimi comes on."},
        {"sequence": 5,  "time": {"displayValue": "70'"}, "text": "Foul by Haiti defender."},
    ]
    sig = analyse_commentary(sample, "Morocco", "Haiti", current_minute=85)
    print("=== NLP Momentum Test ===")
    print(f"Home (Morocco) : momentum={sig.home_momentum:+.4f}  λ_adj={sig.home_lambda_adj}")
    print(f"Away (Haiti)   : momentum={sig.away_momentum:+.4f}  λ_adj={sig.away_lambda_adj}")
    print(f"Dominance      : {sig.dominance}")
    print(f"Urgency        : {sig.urgency_detected}")
    print(f"Signals ({len(sig.signals)}) :")
    for s in sig.signals:
        print(f"  {s}")


class PenaltySignal(NamedTuple):
    home_penalty_adj: float
    away_penalty_adj: float
    home_reasons: list[str]
    away_reasons: list[str]

def extract_live_penalties(commentary: list[dict], home: str, away: str) -> PenaltySignal:
    """
    Analyse l'historique complet d'un match pour trouver les événements 
    pénalisants majeurs (cartons rouges, blessures).
    """
    if not commentary:
        return PenaltySignal(1.0, 1.0, [], [])
        
    home_l = home.lower()
    away_l = away.lower()
    
    h_adj = 1.0
    a_adj = 1.0
    h_reasons = []
    a_reasons = []
    
    # Parcourt tous les commentaires
    for c in commentary:
        txt = c.get("text", "").lower()
        if not txt: continue
        
        # Carton rouge
        if "red card" in txt:
            if home_l in txt:
                h_adj *= 0.85
                h_reasons.append("Carton rouge (-15%)")
            elif away_l in txt:
                a_adj *= 0.85
                a_reasons.append("Carton rouge (-15%)")
                
        # Blessure
        if "injury" in txt and "delay" in txt:
            if home_l in txt:
                h_adj *= 0.95
                h_reasons.append("Blessure (-5%)")
            elif away_l in txt:
                a_adj *= 0.95
                a_reasons.append("Blessure (-5%)")

    return PenaltySignal(
        home_penalty_adj=round(h_adj, 2),
        away_penalty_adj=round(a_adj, 2),
        home_reasons=h_reasons,
        away_reasons=a_reasons
    )
