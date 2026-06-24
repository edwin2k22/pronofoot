import os
import json
import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
COMBO_FILE = os.path.join(DATA_DIR, "combo_history.json")

def load_combo_history():
    if os.path.exists(COMBO_FILE):
        try:
            with open(COMBO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"history": {}, "stats": {"won": 0, "lost": 0, "pending": 0, "winRate": 0}}

def save_combo_history(data):
    with open(COMBO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def update_daily_combo(top_picks, all_matches):
    from collector.models.best_picks import _pick_won
    
    data = load_combo_history()
    today_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    
    # 1. Créer le combiné du jour s'il n'existe pas
    if today_str not in data["history"]:
        lock_picks = [p for p in top_picks.get("picks", []) if p.get("tier") == "lock"]
        
        seen_matches = set()
        combo_legs = []
        for p in lock_picks:
            m_match = None
            for m in all_matches:
                if m["home"] == p["home"] and m["away"] == p["away"]:
                    m_match = m
                    break
            
            # On prend uniquement des matchs pas encore commencés (SCHEDULED) pour le combo du jour
            if not m_match or m_match.get("status") != "SCHEDULED":
                continue
                
            match_key = f"{p['home']}|{p['away']}"
            if match_key in seen_matches:
                continue
            
            seen_matches.add(match_key)
            combo_legs.append({
                "home": p["home"],
                "away": p["away"],
                "market": p["market"],
                "label": p["label"],
                "prob": p["prob"],
                "status": "PENDING"
            })
            
            if len(combo_legs) >= 4:
                break
        
        if combo_legs:
            data["history"][today_str] = {
                "status": "PENDING",
                "legs": combo_legs
            }
            
    # 2. Réévaluer les combinés PENDING existants
    for date_key, combo in data["history"].items():
        if combo["status"] == "PENDING":
            all_finished = True
            any_lost = False
            
            for leg in combo["legs"]:
                if leg["status"] == "PENDING":
                    m_match = None
                    for m in all_matches:
                        if m["home"] == leg["home"] and m["away"] == leg["away"]:
                            m_match = m
                            break
                    
                    if m_match and m_match.get("status") == "FINISHED":
                        won = _pick_won(leg["market"], leg["label"], m_match)
                        if won is True:
                            leg["status"] = "WON"
                        elif won is False:
                            leg["status"] = "LOST"
                            any_lost = True
                        else:
                            leg["status"] = "VOID"
                    else:
                        all_finished = False
                
                elif leg["status"] == "LOST":
                    any_lost = True
                elif leg["status"] == "PENDING":
                    all_finished = False
                    
            if any_lost:
                combo["status"] = "LOST"
            elif all_finished:
                if all(l["status"] == "VOID" for l in combo["legs"]):
                    combo["status"] = "VOID"
                else:
                    combo["status"] = "WON"

    # 3. Recalculer les stats globales
    won_c = sum(1 for c in data["history"].values() if c["status"] == "WON")
    lost_c = sum(1 for c in data["history"].values() if c["status"] == "LOST")
    pending_c = sum(1 for c in data["history"].values() if c["status"] == "PENDING")
    
    total_finished = won_c + lost_c
    win_rate = round((won_c / total_finished) * 100) if total_finished > 0 else 0
    
    data["stats"] = {
        "won": won_c,
        "lost": lost_c,
        "pending": pending_c,
        "winRate": win_rate
    }
    
    save_combo_history(data)
    return data
