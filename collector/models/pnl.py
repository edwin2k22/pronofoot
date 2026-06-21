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
    """ROI de la stratégie VALUE 1N2 et Over/Under."""
    pnl = staked = wins = n = 0
    for m in matches:
        if m["status"] != "FINISHED" or not m.get("analysis"):
            continue
        
        has_1n2 = m.get("odd1") and m.get("oddX") and m.get("odd2")
        has_ou = m.get("oddOU_line") and m.get("oddOver") and m.get("oddUnder")
        if not (has_1n2 or has_ou):
            continue
            
        p = m["prediction"]
        
        # 1N2
        if has_1n2:
            o = _outcome(m["analysis"])
            for k, odd in (("1", m["odd1"]), ("X", m["oddX"]), ("2", m["odd2"])):
                pm = {"1": p["p1"], "X": p["pX"], "2": p["p2"]}[k]
                if pm - 1.0 / odd > edge_min:
                    n += 1; staked += 1
                    if k == o:
                        pnl += odd - 1; wins += 1
                    else:
                        pnl -= 1
                        
        # Over/Under
        if has_ou:
            ou_line = str(m["oddOU_line"])
            if ou_line in p.get("overUnder", {}):
                ou_probs = p["overUnder"][ou_line]
                real_total = m["analysis"]["totalGoals"]
                o_ou = "over" if real_total > m["oddOU_line"] else "under"
                
                for k, odd in (("over", m["oddOver"]), ("under", m["oddUnder"])):
                    pm = ou_probs[k]
                    if pm - 1.0 / odd > edge_min:
                        n += 1; staked += 1
                        if k == o_ou:
                            pnl += odd - 1; wins += 1
                        else:
                            pnl -= 1

        # BTTS
        if m.get("oddBTTS_Yes") and m.get("oddBTTS_No"):
            real_btts = "yes" if m["analysis"]["homeGF"] > 0 and m["analysis"]["awayGF"] > 0 else "no"
            for k, odd in (("yes", m["oddBTTS_Yes"]), ("no", m["oddBTTS_No"])):
                pm = p.get("btts") if k == "yes" else (1 - p.get("btts", 0))
                if pm - 1.0 / odd > edge_min:
                    n += 1; staked += 1
                    if k == real_btts:
                        pnl += odd - 1; wins += 1
                    else:
                        pnl -= 1
                        
        # Corners (if we had real corners data... unfortunately analysis doesn't have real corners yet)
        # So we can't easily calculate historical PnL for corners/cards without the real results.

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
    from datetime import datetime, timezone, timedelta
    
    bets = []
    now = datetime.now(timezone.utc)
    limit_24h = now + timedelta(hours=24)
    
    for m in matches:
        if m["status"] == "FINISHED":
            continue
            
        p = m["prediction"]
        home, away = m["home"], m["away"]
        
        has_1n2 = m.get("odd1") and m.get("oddX") and m.get("odd2")
        has_ou = m.get("oddOU_line") and m.get("oddOver") and m.get("oddUnder")
        has_btts = m.get("oddBTTS_Yes") and m.get("oddBTTS_No")
        has_corners = m.get("oddCorners_line") and m.get("oddCorners_Over")
        has_cards = m.get("oddCards_line") and m.get("oddCards_Over")
        has_shots = m.get("oddShots_line") and m.get("oddShots_Over")
        
        if not (has_1n2 or has_ou or has_btts or has_corners or has_cards or has_shots):
            continue
            
        # Filtrer pour ne garder que les matchs du jour / prochaines 24h
        # Si on ne trouve pas de date valide, on ignore (ou on l'inclut, mais on va l'ignorer pour le top value du jour)
        date_str = m.get("date") or m.get("utcDate")
        if not date_str:
            continue
            
        try:
            # ex: "2026-06-21 12:00 UTC-3"
            parts = date_str.split(" UTC")
            dt_base = datetime.strptime(parts[0].strip(), "%Y-%m-%d %H:%M")
            if len(parts) > 1:
                offset_str = parts[1].strip()
                sign = -1 if offset_str.startswith("-") else 1
                off = int(offset_str.replace("+","").replace("-","").split(":")[0])
                dt_base = dt_base - timedelta(hours=sign * off) # ramener à l'UTC
            dt_utc = dt_base.replace(tzinfo=timezone.utc)
            
            # Ne conserver que si le match est dans le futur et à moins de 24h
            if dt_utc < now or dt_utc > limit_24h:
                continue
        except Exception:
            # si erreur de parsing, on l'exclut du filtre "24h" par sécurité
            continue

        p = m["prediction"]
        home, away = m["home"], m["away"]
        
        # 1N2
        if has_1n2:
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
                        "market": "1N2"
                    })
                    
        # Over/Under
        if has_ou:
            ou_line = str(m["oddOU_line"])
            if ou_line in p.get("overUnder", {}):
                ou_probs = p["overUnder"][ou_line]
                for k, odd, label in (("over", m["oddOver"], f"Plus de {ou_line} buts"),
                                      ("under", m["oddUnder"], f"Moins de {ou_line} buts")):
                    pm = ou_probs[k]
                    implied = 1.0 / odd
                    edge = pm - implied
                    if edge >= edge_min:
                        bets.append({
                            "home": home, "away": away, "date": m.get("date") or m.get("utcDate"),
                            "label": label, "prob": round(pm, 4), "odd": odd,
                            "implied": round(implied, 4), "edge": round(edge, 4),
                            "ev": round(pm * odd - 1, 3),
                            "provider": m.get("oddsProvider"),
                            "market": "O/U"
                        })
                        
        # BTTS
        if has_btts and p.get("btts"):
            for k, odd, label in (("yes", m["oddBTTS_Yes"], "Les deux marquent : Oui"),
                                  ("no", m["oddBTTS_No"], "Les deux marquent : Non")):
                pm = p["btts"] if k == "yes" else (1 - p["btts"])
                implied = 1.0 / odd
                edge = pm - implied
                if edge >= edge_min:
                    bets.append({
                        "home": home, "away": away, "date": m.get("date") or m.get("utcDate"),
                        "label": label, "prob": round(pm, 4), "odd": odd,
                        "implied": round(implied, 4), "edge": round(edge, 4),
                        "ev": round(pm * odd - 1, 3), "provider": "Smarkets", "market": "BTTS"
                    })

        # Corners
        if has_corners and p.get("corners", {}).get("total_mean"):
            import math
            def poisson_cdf(mu, k): return sum(math.exp(-mu) * (mu**i) / math.factorial(i) for i in range(int(k)+1))
            mu = p["corners"]["total_mean"]
            line = m["oddCorners_line"]
            p_under = poisson_cdf(mu, math.floor(line))
            
            for k, odd, label in (("over", m["oddCorners_Over"], f"Plus de {line} corners"),
                                  ("under", m.get("oddCorners_Under"), f"Moins de {line} corners")):
                if not odd: continue
                pm = (1 - p_under) if k == "over" else p_under
                implied = 1.0 / odd
                edge = pm - implied
                if edge >= edge_min:
                    bets.append({
                        "home": home, "away": away, "date": m.get("date") or m.get("utcDate"),
                        "label": label, "prob": round(pm, 4), "odd": odd,
                        "implied": round(implied, 4), "edge": round(edge, 4),
                        "ev": round(pm * odd - 1, 3), "provider": "Smarkets", "market": "Corners"
                    })
                    
        # Tirs (Shots)
        if has_shots and p.get("shots", {}).get("lines"):
            line = str(m["oddShots_line"])
            if line in p["shots"]["lines"]:
                for k, odd, label in (("over", m["oddShots_Over"], f"Plus de {line} tirs (total)"),
                                      ("under", m.get("oddShots_Under"), f"Moins de {line} tirs (total)")):
                    if not odd: continue
                    pm = p["shots"]["lines"][line][k]
                    implied = 1.0 / odd
                    edge = pm - implied
                    if edge >= edge_min:
                        bets.append({
                            "home": home, "away": away, "date": date_str,
                            "label": label, "prob": round(pm, 4), "odd": odd,
                            "implied": round(implied, 4), "edge": round(edge, 4),
                            "ev": round(pm * odd - 1, 3), "provider": "Smarkets", "market": "Tirs"
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
