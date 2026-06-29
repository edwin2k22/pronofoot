import json
import re

path = r'c:\Users\zakro\ZCodeProject\collector\data\predictions.json'
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

for mt in data:
    if mt.get('status') in ('FINISHED', 'HT', 'LIVE') and mt.get('analysis'):
        a = mt['analysis']
        if 'realScore' not in a or not a['realScore']: continue
        try:
            gh, ga = map(int, a['realScore'].split('-'))
        except: continue
        total = gh + ga
        
        ev = a.get('events')
        if not ev: continue
        
        goals = ev.get('goals', [])
        if len(goals) < total and 'commentary' in ev:
            print(f'Match {mt.get("home")} vs {mt.get("away")} has {total} goals but {len(goals)} in goals array.')
            extracted = []
            for c in ev['commentary']:
                if 'type' in c and 'Goal' in c['type']:
                    # Ex: 'Goal! South Africa 0, Canada 1. Stephen Eustaquio (Canada) right footed shot...'
                    # Or 'Goal! Germany 2, Scotland 0. Jamal Musiala (Germany) right footed...'
                    text = c.get('text', '')
                    m = re.search(r'\.\s+([A-Za-z\s\u00C0-\u017F\-\']+)\s+\((.*?)\)', text)
                    if m:
                        player = m.group(1).strip()
                        team = m.group(2).strip()
                        extracted.append({
                            'minute': c.get('minute', ''),
                            'player': player,
                            'team': team,
                            'type': c.get('type')
                        })
            if extracted:
                print('Extracted:', extracted)
                ev['goals'] = extracted

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("Done fixing predictions.json goals!")
