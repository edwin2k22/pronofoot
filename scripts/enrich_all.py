"""Génère/ complète un CSV FIFA-like pour tous les joueurs des effectifs 2026.

Stats synthétiques (pace/shooting/...) basées sur le poste — pas de vraies données
propriétaires. À lancer depuis la RACINE du projet :

    python3 scripts/enrich_all.py
"""
import json
import csv
import os
import random

# scripts/ -> remonte à la racine du projet
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "collector", "data")
SQUADS_PATH = os.path.join(DATA_DIR, "squads_2026.json")
CSV_PATH = os.path.join(DATA_DIR, "players_fifa24.csv")

def run():
    with open(SQUADS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Read existing names in CSV
    existing_names = set()
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_names.add(row.get("short_name", "").lower())
                
    mode = "a" if os.path.exists(CSV_PATH) else "w"
    added = 0
    with open(CSV_PATH, mode, encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if mode == "w":
            writer.writerow(["short_name", "pace", "shooting", "passing", "dribbling", "defending", "physical", "player_traits"])
            
        for squad in data:
            for p in squad["joueurs"]:
                name = p["joueur"]
                if name.lower() not in existing_names:
                    # Generate realistic stats based on position
                    pos = p.get("poste", "MF")
                    if pos == "FW":
                        pac, sho, pas, dri, def_, phy = random.randint(75, 88), random.randint(75, 85), random.randint(60, 75), random.randint(70, 85), random.randint(30, 45), random.randint(60, 80)
                        traits = "Speed Dribbler" if pac > 82 else "Finesse Shot"
                    elif pos == "MF":
                        pac, sho, pas, dri, def_, phy = random.randint(65, 80), random.randint(60, 75), random.randint(75, 85), random.randint(70, 82), random.randint(60, 75), random.randint(65, 80)
                        traits = "Playmaker" if pas > 80 else "Long Passer"
                    elif pos == "DF":
                        pac, sho, pas, dri, def_, phy = random.randint(60, 85), random.randint(30, 50), random.randint(55, 75), random.randint(50, 70), random.randint(75, 85), random.randint(75, 88)
                        traits = "Solid Player" if def_ > 80 else "Power Header"
                    else: # GK
                        pac, sho, pas, dri, def_, phy = random.randint(30, 50), random.randint(10, 20), random.randint(50, 65), random.randint(20, 30), random.randint(10, 20), random.randint(60, 80)
                        traits = "GK Long Throw"
                        
                    writer.writerow([name, pac, sho, pas, dri, def_, phy, traits])
                    existing_names.add(name.lower())
                    added += 1
                
    print(f"Added {added} missing players from all teams to the external CSV database.")

if __name__ == "__main__":
    run()
