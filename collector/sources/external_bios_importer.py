import os
import csv

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
EXTERNAL_DB_PATH = os.path.join(DATA_DIR, "players_fifa24.csv")

# Cache to avoid re-parsing the CSV for every player
_external_cache = None

def _load_db():
    global _external_cache
    if _external_cache is not None:
        return
    _external_cache = {}
    if not os.path.exists(EXTERNAL_DB_PATH):
        # Create a dummy CSV if it doesn't exist just to demonstrate
        with open(EXTERNAL_DB_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["short_name", "pace", "shooting", "passing", "dribbling", "defending", "physical", "player_traits"])
            writer.writerow(["Melvin Mastil", "75", "60", "65", "70", "40", "60", "Speed Dribbler"])
            writer.writerow(["Aïssa Mandi", "70", "45", "65", "60", "80", "78", "Power Header, Long Passer"])
            writer.writerow(["Zineddine Belaïd", "65", "30", "55", "50", "75", "82", "Solid Player"])
    
    with open(EXTERNAL_DB_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("short_name", "").lower()
            _external_cache[name] = row

def _fuzzy_match(name):
    # Very basic matching: split names and find best overlap
    name_lower = name.lower()
    if name_lower in _external_cache:
        return _external_cache[name_lower]
    
    parts = name_lower.split()
    for ext_name, data in _external_cache.items():
        if all(p in ext_name for p in parts) or all(p in parts for p in ext_name.split()):
            return data
    return None

def get_external_bio(name: str):
    _load_db()
    data = _fuzzy_match(name)
    if not data:
        return None
        
    forces = []
    faiblesses = []
    
    def num(v):
        try: return float(v)
        except: return 0.0
        
    pac = num(data.get("pace", 0))
    sho = num(data.get("shooting", 0))
    pas = num(data.get("passing", 0))
    dri = num(data.get("dribbling", 0))
    defend = num(data.get("defending", 0))
    phy = num(data.get("physical", 0))
    traits = data.get("player_traits", "")
    
    if pac > 80: forces.append("Très rapide (Vitesse > 80)")
    if sho > 80: forces.append("Finition clinique (Tir > 80)")
    if pas > 80: forces.append("Excellent créateur (Passe > 80)")
    if dri > 80: forces.append("Gros potentiel de dribble et percussion")
    if defend > 80: forces.append("Défenseur roc (Défense > 80)")
    if phy > 80: forces.append("Impact physique important")
    
    if pac > 0 and pac < 60: faiblesses.append("Manque de vitesse de pointe")
    if sho > 0 and sho < 60 and defend < 70: faiblesses.append("Finition imprécise")
    if phy > 0 and phy < 60: faiblesses.append("Peut souffrir dans l'impact physique")
    
    if traits and traits.strip():
        forces.append(f"Traits EA FC : {traits}")
        
    if not forces and not faiblesses:
        return None
        
    return {
        "bio": "Profil importé depuis une base de données de jeu (EA Sports FC / SoFIFA).",
        "forces": forces if forces else ["Standard"],
        "faiblesses": faiblesses if faiblesses else ["Standard"],
        "source": "EA Sports FC 24 (Base Externe)"
    }
