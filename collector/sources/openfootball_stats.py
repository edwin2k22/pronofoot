from __future__ import annotations
import json
import os
import random
from collector.sources import openfootball_wc

def extract_goals() -> dict:
    """
    Extrait les buteurs directement depuis openfootball worldcup.json.
    Renvoie un dictionnaire : { "Nom du Joueur": {"buts": X, "matches_scored": [match_id]} }
    """
    schedule = openfootball_wc.load_schedule()
    player_goals = {}
    
    for m in schedule.get("matches", []):
        if not openfootball_wc.played(m):
            continue
            
        # Parcourir goals1
        for g in m.get("goals1", []):
            if g.get("owngoal"): continue
            name = g.get("name")
            if not name: continue
            if name not in player_goals:
                player_goals[name] = {"buts": 0, "matches_scored": []}
            player_goals[name]["buts"] += 1
            player_goals[name]["matches_scored"].append(m.get("num", 0))
            
        # Parcourir goals2
        for g in m.get("goals2", []):
            if g.get("owngoal"): continue
            name = g.get("name")
            if not name: continue
            if name not in player_goals:
                player_goals[name] = {"buts": 0, "matches_scored": []}
            player_goals[name]["buts"] += 1
            player_goals[name]["matches_scored"].append(m.get("num", 0))
            
    return player_goals

if __name__ == "__main__":
    goals = extract_goals()
    for player, data in sorted(goals.items(), key=lambda x: x[1]["buts"], reverse=True):
        print(f"{player}: {data['buts']} buts")
