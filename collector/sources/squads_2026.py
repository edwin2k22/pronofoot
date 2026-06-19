"""
Adaptateur #7 — Effectifs OFFICIELS de la Coupe du Monde 2026.

Source : openfootball/worldcup.json (2026/worldcup.squads.json), domaine public, sans clé.
48 sélections × ~26 joueurs = ~1245 joueurs réellement sélectionnés pour 2026.

Rôle dans le stack : fournir les VRAIS joueurs 2026 (numéro, poste, nom, date de
naissance). Leurs STATS de match restent N/D jusqu'à ce qu'un match 2026 soit
disponible dans une source d'events — elles seront remplies par player_ingest.py.
"""
from __future__ import annotations
import os, datetime
from ..http_cache import get_json

RAW = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.squads.json"
CACHE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache", "squads2026.json")


def load_squads(ttl: int = 24 * 3600) -> list[dict]:
    """Liste des 48 sélections avec leurs joueurs (fallback cache local si offline)."""
    data = get_json(RAW, ttl=ttl)
    if data:
        return data
    if os.path.exists(CACHE):
        import json
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    return []


def _age(dob: str | None) -> int | None:
    if not dob:
        return None
    try:
        y, m, d = map(int, dob.split("-"))
        today = datetime.date(2026, 6, 11)   # début du tournoi
        return today.year - y - ((today.month, today.day) < (m, d))
    except Exception:
        return None


def all_players() -> list[dict]:
    """Aplati : un dict par joueur, avec son équipe/groupe."""
    out = []
    for team in load_squads():
        tname = team.get("name", "?")
        for p in team.get("players", []):
            out.append({
                "team": tname,
                "fifa_code": team.get("fifa_code", ""),
                "group": team.get("group", ""),
                "number": p.get("number"),
                "name": p.get("name", "?"),
                "pos": p.get("pos", "?"),
                "dob": p.get("date_of_birth"),
                "age": _age(p.get("date_of_birth")),
            })
    return out
