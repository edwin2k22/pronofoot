import json
try:
    with open('data/matches.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    for m in data:
        if m['status'] == 'FINISHED':
            print(f"{m['homeTeam']['name']} vs {m['awayTeam']['name']} | Score HT: {m.get('score', {}).get('halfTime')}")
            break
except Exception as e:
    print("Error matches.json:", e)

try:
    with open('collector/data/matches.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    for m in data:
        if m['status'] == 'FINISHED':
            print(f"{m['homeTeam']['name']} vs {m['awayTeam']['name']} | Score HT: {m.get('score', {}).get('halfTime')}")
            break
except Exception as e:
    print("Error collector/data/matches.json:", e)

try:
    with open('collector/data/match_stats_real.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    for m in data:
        print(f"Stats file item keys: {list(m.keys())}")
        break
except Exception as e:
    pass
