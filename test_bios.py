import json

with open('collector/data/squads_2026.json', encoding='utf-8') as f:
    data = json.load(f)

for p in data[0]['joueurs'][:5]:
    bio = p.get("bio", {})
    if isinstance(bio, dict):
        print(p["joueur"], "-", bio.get("forces", []), "- Source:", bio.get("source"))
    else:
        print(p["joueur"], "- No bio")
