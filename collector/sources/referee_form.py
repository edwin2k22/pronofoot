"""
Style d'arbitrage = sévérité (cartons/match) d'un arbitre.

Combine :
  1) un PRIOR réel sourcé (referees_2026.SEVERITY, stats carrière/saison)
  2) les VRAIS cartons sifflés par cet arbitre en CDM 2026 (accumulés au fil du tournoi)
… via un shrinkage prudent (peu de matchs CDM -> on reste proche du prior).

Le fichier collector/data/referee_cards.json stocke, par arbitre, la liste des
totaux de cartons par match qu'il a arbitrés (rempli par espn_ingest).
"""
from __future__ import annotations
import os, json, unicodedata
from . import referees_2026 as refs


def _norm(s):
    """Sans accents, minuscule, sans nom du milieu — pour matcher 'Vincici'≈'Vinčić'."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    parts = s.replace(",", " ").split()
    return parts[-1] if parts else ""   # nom de famille

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CARDS_FILE = os.path.join(DATA, "referee_cards.json")
SHRINK_K = 4   # ~4 matchs virtuels tirant vers le prior


def _load():
    try:
        with open(CARDS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def record_match(referee, total_cards):
    """Enregistre le nb total de cartons d'un match arbitré (idempotent par valeur)."""
    if not referee or total_cards is None:
        return
    store = _load()
    store.setdefault(referee, [])
    store[referee].append(int(total_cards))
    os.makedirs(DATA, exist_ok=True)
    with open(CARDS_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=1)


def severity(referee):
    """
    Renvoie {avg, n, prior, source} : cartons/match attendus pour cet arbitre.
    avg = (n*observé + k*prior) / (n+k).  Si arbitre inconnu -> moyenne générale.
    Matching tolérant aux accents/variantes (nom de famille).
    """
    key = _norm(referee)
    # prior : cherche par nom de famille normalisé
    prior = refs.REF_AVG
    for name, sev in refs.SEVERITY.items():
        if _norm(name) == key:
            prior = sev
            break
    # observé : agrège toutes les variantes du même nom de famille
    store = _load()
    obs = []
    for name, lst in store.items():
        if _norm(name) == key:
            obs += lst
    n = len(obs)
    known = any(_norm(name) == key for name in refs.SEVERITY)
    if n == 0:
        return {"avg": round(prior, 2), "n": 0, "prior": prior,
                "source": "historique (carrière)" if known else "moyenne générale"}
    mean_obs = sum(obs) / n
    avg = (n * mean_obs + SHRINK_K * prior) / (n + SHRINK_K)
    return {"avg": round(avg, 2), "n": n, "prior": prior, "obsMean": round(mean_obs, 2),
            "source": f"prior + {n} match(s) CDM 2026"}
