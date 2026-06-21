"""
Adaptateur Smarkets — Cotes d'échange pour les marchés alternatifs (BTTS, Corners, Cartons).

Source : API publique Smarkets (api.smarkets.com), GRATUITE, sans clé.
Retourne des données pures JSON. Les cotes (quotes) sont sous forme de probabilité implicite.
"""

from __future__ import annotations
import json, urllib.request, time

BASE = "https://api.smarkets.com/v3"
UA = {"User-Agent": "Mozilla/5.0 (PronoFoot Smarkets Collector)"}
TIMEOUT = 15

def _get(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print(f"[Smarkets] Erreur GET {url}: {e}")
        return None

def _price_to_odds(price):
    if not price or price <= 0: return 0
    return round(10000 / price, 2)

def _match_teams(zcode_home, zcode_away, smarkets_name):
    if " vs " not in smarkets_name: return False
    s_home, s_away = smarkets_name.split(" vs ", 1)
    def _normalize(name):
        return name.lower().replace("dr congo", "congo dr").replace("bosnia & herzegovina", "bosnia")
    z_home_n, z_away_n = _normalize(zcode_home), _normalize(zcode_away)
    s_home_n, s_away_n = s_home.lower(), s_away.lower()
    return (z_home_n in s_home_n or s_home_n in z_home_n) and (z_away_n in s_away_n or s_away_n in z_away_n)

def fetch_events(limit=100):
    url = f"{BASE}/events/?state=upcoming&type=football_match&limit={limit}"
    data = _get(url)
    return data["events"] if data and "events" in data else []

def chunk(lst, n):
    for i in range(0, len(lst), n): yield lst[i:i + n]

def get_match_odds(db_matches):
    print("[Smarkets] Récupération des matchs à venir...")
    events = fetch_events(200)
    if not events: return {}
        
    matched_events = {}
    for m in db_matches:
        try:
            home = m["home"]
            away = m["away"]
        except (KeyError, IndexError, TypeError):
            continue
            
        for e in events:
            if _match_teams(home, away, e.get("name", "")):
                matched_events[e["id"]] = f"{home}|{away}"
                break
                
    if not matched_events:
        print("[Smarkets] Aucun match ne correspond.")
        return {}
        
    print(f"[Smarkets] {len(matched_events)} matchs liés.")
    
    market_to_event = {}
    market_info = {}
    market_ids = []
    
    for batch in chunk(list(matched_events.keys()), 10):
        m_data = _get(f"{BASE}/events/{','.join(batch)}/markets/")
        time.sleep(0.5)
        if m_data and "markets" in m_data:
            for mk in m_data["markets"]:
                cat, name = mk.get("category"), mk.get("name", "")
                is_btts = (mk.get("market_type", {}).get("name") == "BTTS") or (name == "Both teams to score")
                is_corners = (cat == "corners" and "over/under" in name.lower())
                is_cards = (cat == "cards" and "over/under" in name.lower())
                is_shots = (cat == "shots" and "over/under" in name.lower())
                if is_btts or is_corners or is_cards or is_shots:
                    market_to_event[mk["id"]] = mk["event_id"]
                    market_ids.append(mk["id"])
                    market_info[mk["id"]] = mk

    if not market_ids: return {}

    contract_to_info = {}
    for batch in chunk(market_ids, 40):
        c_data = _get(f"{BASE}/markets/{','.join(batch)}/contracts/")
        time.sleep(0.5)
        if c_data and "contracts" in c_data:
            for c in c_data["contracts"]:
                contract_to_info[c["id"]] = {"name": c["name"], "market_id": c["market_id"]}

    results = { m_id: {} for m_id in matched_events.values() }
    
    for batch in chunk(market_ids, 40):
        q_data = _get(f"{BASE}/markets/{','.join(batch)}/quotes/")
        time.sleep(0.5)
        if not q_data: continue
        
        for mk_id, mk_quotes in q_data.items():
            ev_id = market_to_event.get(mk_id)
            if not ev_id: continue
            db_id = matched_events[ev_id]
            mk_inf = market_info[mk_id]
            
            for contract_id, quotes in mk_quotes.items():
                if contract_id not in contract_to_info: continue
                c_name = contract_to_info[contract_id]["name"].lower()
                
                offers = quotes.get("offers", [])
                if not offers: continue
                
                best_price = min(o["price"] for o in offers)
                odd_decimal = _price_to_odds(best_price)
                if odd_decimal == 0: continue
                
                # BTTS
                if mk_inf.get("market_type", {}).get("name") == "BTTS" or mk_inf.get("name") == "Both teams to score":
                    if "yes" in c_name: results[db_id]["oddBTTS_Yes"] = odd_decimal
                    elif "no" in c_name: results[db_id]["oddBTTS_No"] = odd_decimal
                
                # Corners
                elif mk_inf.get("category") == "corners" and "over/under" in mk_inf.get("name", "").lower():
                    parts = mk_inf.get("name", "").split()
                    try:
                        line = float([p for p in parts if "." in p][0])
                        results[db_id]["oddCorners_line"] = line
                        if "over" in c_name: results[db_id]["oddCorners_Over"] = odd_decimal
                        elif "under" in c_name: results[db_id]["oddCorners_Under"] = odd_decimal
                    except: pass
                    
                # Cards
                elif mk_inf.get("category") == "cards" and "over/under" in mk_inf.get("name", "").lower():
                    parts = mk_inf.get("name", "").split()
                    try:
                        line = float([p for p in parts if "." in p][0])
                        results[db_id]["oddCards_line"] = line
                        if "over" in c_name: results[db_id]["oddCards_Over"] = odd_decimal
                        elif "under" in c_name: results[db_id]["oddCards_Under"] = odd_decimal
                    except: pass
                    
                # Shots
                elif mk_inf.get("category") == "shots" and "over/under" in mk_inf.get("name", "").lower():
                    parts = mk_inf.get("name", "").split()
                    try:
                        line = float([p for p in parts if "." in p][0])
                        results[db_id]["oddShots_line"] = line
                        if "over" in c_name: results[db_id]["oddShots_Over"] = odd_decimal
                        elif "under" in c_name: results[db_id]["oddShots_Under"] = odd_decimal
                    except: pass

    return results
