import json, os

STATS_FILE = "collector/data/match_stats_real.json"

try:
    with open(STATS_FILE, encoding="utf-8") as f:
        stats = json.load(f)
except (OSError, ValueError):
    stats = {}

referees = {
    "England|DR Congo": "Adham Makhadmeh",
    "Belgium|Senegal": "Saíd Martínez",
    "USA|Bosnia & Herzegovina": "Raphael Claus"
}

for key, ref in referees.items():
    cur = stats.get(key, {})
    cur["referee"] = ref
    stats[key] = cur

with open(STATS_FILE, "w", encoding="utf-8") as f:
    json.dump(stats, f, ensure_ascii=False, indent=1)

print("Referees updated successfully.")
