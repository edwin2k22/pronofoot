import json

with open('collector/data/predictions.json', encoding='utf-8') as f:
    preds = json.load(f)

print('=== ARBITRES DU 26 JUIN ===')
for m in preds:
    d = m.get('date', '')
    if '2026-06-26' in d:
        ref = m['prediction'].get('referee')
        ref_name = ref.get('name', 'AUCUN') if ref else 'AUCUN'
        sev = ref.get('cardsAvg', '-') if ref else '-'
        print(f"  {m['home']:20s} vs {m['away']:20s} | Arb: {ref_name:25s} | Severite: {sev}")
