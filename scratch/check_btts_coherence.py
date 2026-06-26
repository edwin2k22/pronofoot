import json

with open('collector/data/predictions.json', encoding='utf-8') as f:
    preds = json.load(f)

for m in preds:
    p = m['prediction']
    ts = p.get('topScore', [0,0])
    btts = p.get('btts', 0)
    
    # Check if top score implies no BTTS, but btts prob > 0.5
    if (ts[0] == 0 or ts[1] == 0) and btts > 0.5:
        print(f"Match: {m['home']} vs {m['away']}")
        print(f"  Score: {ts[0]}-{ts[1]}, BTTS Prob: {btts:.3f}")
        print(f"  lamHome: {p.get('lamHome')}, lamAway: {p.get('lamAway')}")
