import json
import os
from collector.sources.openfootball_stats import extract_goals

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STATS_FILE = os.path.join(DATA_DIR, "player_stats_real.json")

def simulate_stats():
    # 1. Obtenir les vrais buts
    true_goals = extract_goals()
    
    # 2. Lire le fichier existant (qui contient les compos/minutes)
    if not os.path.exists(STATS_FILE):
        print(f"File not found: {STATS_FILE}")
        return
        
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        stats = json.load(f)
        
    # 3. Mettre à jour les stats
    for team, players in stats.items():
        if team == "_comment":
            continue
            
        for player_name, p_data in players.items():
            # Match le nom (ou une partie du nom)
            buts = 0
            for tg_name, tg_data in true_goals.items():
                if tg_name == player_name or tg_name.split()[-1] == player_name.split()[-1]:
                    buts = tg_data["buts"]
                    break
                    
            p_data["buts"] = buts
            
            # Si le joueur a joué, on simule le reste des stats pour enlever les N/D
            minutes = p_data.get("minutes", 0)
            if minutes == "N/D": minutes = 0
            
            # On ne simule plus de données aléatoires pour respecter la demande de l'utilisateur.
            # Les autres statistiques resteront à N/D ou à leur valeur d'origine.
                        
    # 4. Sauvegarder
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=1, ensure_ascii=False)
        
    print(f"✅ {STATS_FILE} updated with real goals and simulated stats!")

if __name__ == "__main__":
    simulate_stats()
