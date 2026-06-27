import requests
import csv
import io

URL = "https://raw.githubusercontent.com/prashantghimire/sofifa-web-scraper/master/player_stats.csv"

def compute_avg(row, cols):
    try:
        vals = [float(row[c]) for c in cols if row.get(c)]
        if vals: return int(sum(vals) / len(vals))
        return 0
    except:
        return 0

print("Downloading FC 26 dataset...")
r = requests.get(URL)
r.raise_for_status()

reader = csv.DictReader(io.StringIO(r.text))
out_rows = []

for row in reader:
    name = row.get('name', '')
    # The scraped CSV has some mojibake for special characters like  (U+FFFD). We will just keep it and let fuzzy match handle the rest.
    if not name: continue
    
    pace = compute_avg(row, ['movement_acceleration', 'movement_sprint_speed'])
    sho = compute_avg(row, ['attacking_finishing', 'power_shot_power', 'power_long_shots', 'attacking_volleys', 'mentality_att_positioning'])
    pas = compute_avg(row, ['attacking_short_passing', 'skill_long_passing', 'attacking_crossing', 'mentality_vision', 'skill_curve'])
    dri = compute_avg(row, ['movement_agility', 'movement_balance', 'movement_reactions', 'skill_ball_control', 'skill_dribbling'])
    dfn = compute_avg(row, ['mentality_interceptions', 'attacking_heading_accuracy', 'defending_defensive_awareness', 'defending_standing_tackle', 'defending_sliding_tackle'])
    phy = compute_avg(row, ['power_jumping', 'power_stamina', 'power_strength', 'mentality_aggression'])
    
    traits = row.get('play_styles', '')
    
    out_rows.append({
        'short_name': name,
        'pace': pace,
        'shooting': sho,
        'passing': pas,
        'dribbling': dri,
        'defending': dfn,
        'physical': phy,
        'player_traits': traits
    })

out_path = "collector/data/players_fifa26.csv"
with open(out_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=['short_name', 'pace', 'shooting', 'passing', 'dribbling', 'defending', 'physical', 'player_traits'])
    writer.writeheader()
    writer.writerows(out_rows)

print(f"Saved {len(out_rows)} players to {out_path}!")
