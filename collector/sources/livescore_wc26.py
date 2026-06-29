"""
Adaptateur #8 — Live scores temps réel CDM 2026 (worldcup26.ir).

API REST gratuite, SANS clé, dédiée à la Coupe du Monde 2026, avec mise à jour
en temps réel pendant les matchs (plus rapide qu'openfootball, qui est quotidien).

Source : https://worldcup26.ir/get/games  (repo : github.com/rezarahiminia/worldcup2026)

Rôle : alimenter le mode LIVE automatiquement. On en tire le score + l'état
(live / terminé). Les stats détaillées (xG, corners…) ne sont pas dans ce flux ;
elles restent saisissables via collector.live --set si besoin.
"""
from __future__ import annotations
from ..http_cache import get_json, RateLimiter

URL = "https://worldcup26.ir/get/games"
_limiter = RateLimiter(max_calls=20, period=60)

# noms worldcup26.ir -> noms openfootball (pour matcher la base)
NAME_FIX = {
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    "Turkiye": "Turkey", "Türkiye": "Turkey",
    "Korea Republic": "South Korea", "IR Iran": "Iran",
    "United States": "USA", "Czechia": "Czech Republic",
    "Cote d'Ivoire": "Ivory Coast", "Côte d'Ivoire": "Ivory Coast",
    "Cabo Verde": "Cape Verde", "Curacao": "Curaçao",
}


def _fix(name: str) -> str:
    return NAME_FIX.get(name, name)


def _int(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def fetch_live(ttl: int = 30) -> list[dict]:
    """
    Renvoie une liste de matchs normalisés :
      {home, away, home_score, away_score, state}
    state ∈ {SCHEDULED, LIVE, FINISHED}. ttl court (30s) pour le temps réel.
    """
    data = get_json(URL, limiter=_limiter, ttl=ttl)
    if not data:
        return []
    games = data.get("games") if isinstance(data, dict) else data
    out = []
    for g in games or []:
        finished = str(g.get("finished", "")).upper() == "TRUE"
        elapsed = str(g.get("time_elapsed", "")).lower()
        hs, as_ = _int(g.get("home_score")), _int(g.get("away_score"))
        if finished:
            state = "FINISHED"
        elif elapsed in ("live", "1h", "2h", "ht", "et") or (
                hs is not None and elapsed not in ("notstarted", "")):
            state = "LIVE"
        else:
            state = "SCHEDULED"
        minute_str = None
        if elapsed not in ("finished", "notstarted", "live"):
            if elapsed == "ht":
                minute_str = "Mi-temps"
            elif elapsed == "et":
                minute_str = "Prolongation"
            elif elapsed == "pen":
                minute_str = "Tirs au but"
            else:
                minute_str = elapsed

        out.append({
            "home": _fix(g.get("home_team_name_en", "")),
            "away": _fix(g.get("away_team_name_en", "")),
            "home_score": hs, "away_score": as_,
            "state": state,
            "minute": minute_str,
        })
    return out
