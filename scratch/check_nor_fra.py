import json

with open('collector/data/predictions.json', encoding='utf-8') as f:
    preds = json.load(f)

for m in preds:
    if m['home'] == 'Norway' and m['away'] == 'France':
        p = m['prediction']
        print(f"bttsConf: {p.get('bttsConf')}")
