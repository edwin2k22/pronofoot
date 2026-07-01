import json

def test():
    with open('collector/data/match_events_real.json', encoding="utf-8") as f:
        events = json.load(f)
    
    key = "Brazil|Japan"
    ev = dict(events.get(key) or {})
    print(f"ev for {key}:", list(ev.keys()))
    print("goals:", ev.get("goals"))
    
    ev_json = json.dumps(ev, ensure_ascii=False) if ev else None
    print("ev_json:", ev_json[:100], "...")

test()
