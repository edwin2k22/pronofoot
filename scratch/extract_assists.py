import json
import re

path = r'c:\Users\zakro\ZCodeProject\collector\data\predictions.json'
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

for mt in data:
    if mt.get('status') in ('FINISHED', 'HT', 'LIVE') and mt.get('analysis'):
        ev = mt['analysis'].get('events')
        if not ev: continue
        goals = ev.get('goals', [])
        
        for g in goals:
            if not g.get('assist'):
                minute = g.get('minute')
                player = g.get('player')
                if 'commentary' in ev:
                    for c in ev['commentary']:
                        if c.get('minute') == minute and 'Goal' in c.get('type', ''):
                            text = c.get('text', '')
                            m = re.search(r'Assisted by\s+([A-Za-z\s\u00C0-\u017F\-\']+?)(?:\s+with|\s+following|\.|$)', text)
                            if m:
                                g['assist'] = m.group(1).strip()
                                print(f"Found assist for {player}: {g['assist']}")
                            break

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('Updated assists in predictions.json!')
