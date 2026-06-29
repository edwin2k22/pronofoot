import json
import re

path = r'c:\Users\zakro\ZCodeProject\collector\data\predictions.json'
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

for mt in data:
    if mt.get('status') in ('FINISHED', 'HT', 'LIVE') and mt.get('analysis'):
        ev = mt['analysis'].get('events')
        if not ev or 'commentary' not in ev: continue
        
        key_events = []
        for c in ev['commentary']:
            text = c.get('text', '')
            minute = c.get('minute', '')
            
            # Injury
            if 'injury' in text and 'Delay' in text:
                m = re.search(r'injury\s+([A-Za-z\s\u00C0-\u017F\-\']+?)\s+\((.*?)\)', text)
                if m:
                    key_events.append({
                        'minute': minute,
                        'type': 'injury',
                        'player': m.group(1).strip(),
                        'team': m.group(2).strip(),
                        'desc': '🚑 Blessure'
                    })
            
            # Card context
            elif 'yellow card' in text or 'red card' in text:
                m = re.search(r'([A-Za-z\s\u00C0-\u017F\-\']+)\s+\((.*?)\).*?(yellow card|red card)\s+for\s+(.*?)\.', text)
                if m:
                    color = "🟨" if "yellow" in m.group(3) else "🟥"
                    reason = m.group(4).strip()
                    # translate reason
                    reason_fr = reason
                    if "bad foul" in reason: reason_fr = "faute d'antijeu"
                    elif "time wasting" in reason: reason_fr = "gain de temps"
                    elif "argument" in reason: reason_fr = "contestation"
                    elif "foul" in reason: reason_fr = "faute"
                    elif "hand ball" in reason or "handball" in reason: reason_fr = "main"
                    elif "dive" in reason: reason_fr = "simulation"
                    elif "professional foul" in reason: reason_fr = "faute professionnelle"
                    
                    key_events.append({
                        'minute': minute,
                        'type': 'card',
                        'player': m.group(1).strip(),
                        'team': m.group(2).strip(),
                        'desc': f"{color} Carton ({reason_fr})"
                    })
                    
        if key_events:
            ev['key_events'] = key_events

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('Extracted key events!')
