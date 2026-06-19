"""
Adaptateur — openfootball/worldcup.json (CALENDRIER RÉEL de la CDM 2026).

Données publiques (domaine public CC0), JSON téléchargeable, SANS clé API.
Source : https://github.com/openfootball/worldcup.json  (fichier 2026/worldcup.json)

Rôle : la colonne vertébrale de l'app — les 104 vrais matchs, dates, groupes,
et scores au fur et à mesure qu'ils sont joués. Le pipeline lit `load_schedule()`
puis construit lui-même les fixtures en base (voir collector/pipeline.py).
"""
from __future__ import annotations
import os, json
from ..http_cache import get_json

RAW = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
CACHE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache", "worldcup2026.json")


def load_schedule(ttl: int = 6 * 3600) -> dict:
    """Charge le calendrier (cache `ttl`s ; fallback sur le fichier local si offline)."""
    data = get_json(RAW, ttl=ttl)
    if data:
        return data
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {"name": "World Cup 2026", "matches": []}


def played(match: dict) -> bool:
    """True si le match a un score final."""
    return bool(match.get("score", {}).get("ft"))
