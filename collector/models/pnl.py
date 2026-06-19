"""
PnL / ROI (Yield) — la métrique reine.

Un taux de réussite élevé ne signifie RIEN sans le rendement : gagner 64 % à cote
1.40 fait perdre de l'argent. Ce module mesure, sur les matchs DÉJÀ JOUÉS et à
partir des VRAIES cotes, le profit/perte en unités (mise = 1u) et le Yield (ROI).

Deux stratégies :
  • value   : parier 1u sur chaque sélection 1N2 où proba_modèle > 1/cote + marge
  • picks   : parier 1u sur les « Meilleurs Choix » (DC/DNB/OU/BTTS…) quand une cote
              de référence existe (ici on couvre DC, DNB, OU2.5, BTTS via les cotes 1N2
              dérivées quand possible, sinon on évalue uniquement la réussite/echec).

Tout est RÉEL. Si aucune cote n'existe pour un marché, il n'est pas compté (jamais
de cote inventée). Yield = PnL / total_misé × 100.
"""
from __future__ import annotations


def _outcome(a):
    hg, ag = map(int, a["realScore"].split("-"))
    return "1" if hg > ag else ("2" if ag > hg else "X")


def value_pnl(matches, edge_min=0.0):
    """ROI de la stratégie VALUE 1N2 (proba modèle > 1/cote + edge_min)."""
    pnl = staked = wins = n = 0
    for m in matches:
        if m["status"] != "FINISHED" or not m.get("analysis"):
            continue
        if not (m.get("odd1") and m.get("oddX") and m.get("odd2")):
            continue
        p = m["prediction"]; o = _outcome(m["analysis"])
        for k, odd in (("1", m["odd1"]), ("X", m["oddX"]), ("2", m["odd2"])):
            pm = {"1": p["p1"], "X": p["pX"], "2": p["p2"]}[k]
            if pm - 1.0 / odd > edge_min:
                n += 1; staked += 1
                if k == o:
                    pnl += odd - 1; wins += 1
                else:
                    pnl -= 1
    return {"bets": n, "wins": wins,
            "winRate": round(100 * wins / n) if n else None,
            "pnl": round(pnl, 2),
            "yield": round(100 * pnl / staked, 1) if staked else None}


def favorite_pnl(matches):
    """ROI si l'on parie naïvement le favori 1N2 du modèle (pour comparaison)."""
    pnl = staked = wins = n = 0
    for m in matches:
        if m["status"] != "FINISHED" or not m.get("analysis"):
            continue
        if not (m.get("odd1") and m.get("oddX") and m.get("odd2")):
            continue
        p = m["prediction"]; o = _outcome(m["analysis"])
        cand = {"1": (p["p1"], m["odd1"]), "X": (p["pX"], m["oddX"]), "2": (p["p2"], m["odd2"])}
        pick = max(cand, key=lambda k: cand[k][0]); odd = cand[pick][1]
        n += 1; staked += 1
        if pick == o:
            pnl += odd - 1; wins += 1
        else:
            pnl -= 1
    return {"bets": n, "wins": wins,
            "winRate": round(100 * wins / n) if n else None,
            "pnl": round(pnl, 2),
            "yield": round(100 * pnl / staked, 1) if staked else None}


def top_value_bets(matches, top=3, edge_min=0.03):
    """
    Les meilleures VALUE BETS du moment (matchs à venir) : plus gros écart
    proba_modèle vs cote implicite. Renvoie une liste triée par edge décroissant.
    """
    bets = []
    for m in matches:
        if m["status"] == "FINISHED":
            continue
        if not (m.get("odd1") and m.get("oddX") and m.get("odd2")):
            continue
        p = m["prediction"]
        home, away = m["home"], m["away"]
        for k, odd, label in (("1", m["odd1"], f"Victoire {home}"),
                              ("X", m["oddX"], "Match nul"),
                              ("2", m["odd2"], f"Victoire {away}")):
            pm = {"1": p["p1"], "X": p["pX"], "2": p["p2"]}[k]
            implied = 1.0 / odd
            edge = pm - implied
            if edge >= edge_min:
                bets.append({
                    "home": home, "away": away, "date": m.get("date"),
                    "label": label, "prob": round(pm, 4), "odd": odd,
                    "implied": round(implied, 4), "edge": round(edge, 4),
                    "ev": round(pm * odd - 1, 3),   # espérance par unité misée
                    "provider": m.get("oddsProvider"),
                })
    bets.sort(key=lambda x: -x["edge"])
    return bets[:top]


def build_pnl(matches):
    """Synthèse complète pour l'app."""
    fav = favorite_pnl(matches)
    val = value_pnl(matches, edge_min=0.0)
    val5 = value_pnl(matches, edge_min=0.05)
    n_odds = sum(1 for m in matches
                 if m["status"] == "FINISHED" and m.get("analysis") and m.get("odd1"))
    return {
        "sampleWithOdds": n_odds,
        "favorite": fav,        # parier le favori (référence)
        "value": val,           # stratégie value (edge>0)
        "valueStrict": val5,    # value plus sélective (edge>5%)
        "topValue": top_value_bets(matches, top=3, edge_min=0.03),
    }
