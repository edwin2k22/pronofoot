import sys, os, json
import sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector.db import database as db
from collector import pipeline
from collector.models import elo as elo_mod
from collector.models import shrinkage as shr

def reset_teams():
    conn = db.init_db()
    conn.execute("""
        UPDATE teams SET 
            elo = fifa_prior, matches_played = 0,
            gf_avg = 1.35, ga_avg = 1.35, xg_avg = 1.35, xga_avg = 1.35,
            corners_avg = 5.0, cards_avg = 2.0,
            shots_avg = 12.0, shots_against_avg = 12.0,
            shots_on_avg = 4.2, shots_on_against_avg = 4.2,
            possession_avg = 50.0, fouls_avg = 10.0
    """)
    conn.execute("DELETE FROM rating_history")
    from collector.sources import recent_form as rform
    for t in conn.execute("SELECT name FROM teams").fetchall():
        ff = rform.team_form(t["name"])
        if ff:
            conn.execute("UPDATE teams SET gf_avg=?, ga_avg=? WHERE name=?", (ff["gf_avg"], ff["ga_avg"], t["name"]))
    conn.execute("UPDATE matches SET processed = 0")
    conn.commit()
    conn.close()

def main():
    print("Resetting database to day 0...")
    reset_teams()
    pred_path = os.path.join(pipeline.DATA_DIR, "predictions.json")
    if os.path.exists(pred_path): 
        if os.path.exists(pred_path + ".bak"):
            os.remove(pred_path + ".bak")
        os.rename(pred_path, pred_path + ".bak")
    
    conn = db.init_db()
    matches = conn.execute("SELECT * FROM matches ORDER BY utc_date").fetchall()
    conn.close()
    
    hist_preds = {}
    print(f"Replaying {len(matches)} matches chronologically...")
    for mt in matches:
        if mt["competition"] != "CDM 2026": continue
        if mt["status"] not in ("FINISHED", "LIVE", "HT"): continue
        
        import time
        for _ in range(5):
            try:
                with open(pred_path, "w", encoding="utf-8") as f: json.dump([], f)
                break
            except OSError:
                time.sleep(0.1)
        
        pipeline.predict()
        
        for _ in range(5):
            try:
                with open(pred_path, "r", encoding="utf-8") as f:
                    all_preds_now = json.load(f)
                break
            except OSError:
                time.sleep(0.1)
            
        my_pred = next((p for p in all_preds_now if p["home"] == mt["home"] and p["away"] == mt["away"]), None)
        if my_pred:
            hist_preds[mt["id"]] = my_pred
            
        # Update DB for this match
        conn = db.init_db()
        h, a = db.get_team(conn, mt["home"]), db.get_team(conn, mt["away"])
        if not h or not a or mt["home_goals"] is None or mt["away_goals"] is None:
            db.mark_processed(conn, mt["id"]); conn.close(); continue
            
        new_h, new_a = elo_mod.update_pair(h["elo"], a["elo"], mt["home_goals"], mt["away_goals"], mt["home_xg"], mt["away_xg"], h["matches_played"], a["matches_played"])
        db.log_rating(conn, h["name"], mt["id"], h["elo"], new_h, "match result")
        db.log_rating(conn, a["name"], mt["id"], a["elo"], new_a, "match result")

        gh, ga = mt["home_goals"], mt["away_goals"]
        hm_gf, _ = shr.update_running_mean(h["gf_avg"], h["matches_played"], gh)
        hm_ga, _ = shr.update_running_mean(h["ga_avg"], h["matches_played"], ga)
        am_gf, _ = shr.update_running_mean(a["gf_avg"], a["matches_played"], ga)
        am_ga, _ = shr.update_running_mean(a["ga_avg"], a["matches_played"], gh)
        hxg, axg = mt["home_xg"], mt["away_xg"]
        hm_xg = shr.update_running_mean(h["xg_avg"], h["matches_played"], hxg)[0] if hxg is not None else h["xg_avg"]
        hm_xga = shr.update_running_mean(h["xga_avg"], h["matches_played"], axg)[0] if axg is not None else h["xga_avg"]
        am_xg = shr.update_running_mean(a["xg_avg"], a["matches_played"], axg)[0] if axg is not None else a["xg_avg"]
        am_xga = shr.update_running_mean(a["xga_avg"], a["matches_played"], hxg)[0] if hxg is not None else a["xga_avg"]

        def _rm(team, col, val): return shr.update_running_mean(team[col], team["matches_played"], val)[0] if val is not None else team[col]
        hs, as_ = mt["home_shots"], mt["away_shots"]
        hso, aso = mt["home_shots_on"], mt["away_shots_on"]
        h_shots = _rm(h, "shots_avg", hs); h_shots_ag = _rm(h, "shots_against_avg", as_)
        h_son = _rm(h, "shots_on_avg", hso); h_son_ag = _rm(h, "shots_on_against_avg", aso)
        a_shots = _rm(a, "shots_avg", as_); a_shots_ag = _rm(a, "shots_against_avg", hs)
        a_son = _rm(a, "shots_on_avg", aso); a_son_ag = _rm(a, "shots_on_against_avg", hso)
        _ts = {}
        if "team_stats_json" in mt.keys() and mt["team_stats_json"]:
            try: _ts = json.loads(mt["team_stats_json"])
            except: pass
        h_poss = _rm(h, "possession_avg", _ts.get("home_possession"))
        a_poss = _rm(a, "possession_avg", _ts.get("away_possession"))
        h_fouls = _rm(h, "fouls_avg", _ts.get("home_fouls"))
        a_fouls = _rm(a, "fouls_avg", _ts.get("away_fouls"))

        conn.execute("""UPDATE teams SET elo=?, gf_avg=?, ga_avg=?, xg_avg=?, xga_avg=?,
                        shots_avg=?, shots_against_avg=?, shots_on_avg=?, shots_on_against_avg=?,
                        possession_avg=?, fouls_avg=?, matches_played=matches_played+1, updated_at=? WHERE name=?""",
                     (new_h, hm_gf, hm_ga, hm_xg, hm_xga, h_shots, h_shots_ag, h_son, h_son_ag, h_poss, h_fouls, db.now(), h["name"]))
        conn.execute("""UPDATE teams SET elo=?, gf_avg=?, ga_avg=?, xg_avg=?, xga_avg=?,
                        shots_avg=?, shots_against_avg=?, shots_on_avg=?, shots_on_against_avg=?,
                        possession_avg=?, fouls_avg=?, matches_played=matches_played+1, updated_at=? WHERE name=?""",
                     (new_a, am_gf, am_ga, am_xg, am_xga, a_shots, a_shots_ag, a_son, a_son_ag, a_poss, a_fouls, db.now(), a["name"]))
        db.mark_processed(conn, mt["id"]); conn.commit(); conn.close()
        print(f"Replayed {mt['home']} vs {mt['away']} (Elo H: {new_h:.1f}, A: {new_a:.1f})")

    # The frozen predictions MUST contain "id" for pipeline.py to find it!
    for mid, mdict in hist_preds.items():
        mdict["id"] = mid
        
    print("Writing historical predictions.json...")
    with open(pred_path, "w", encoding="utf-8") as f:
        json.dump(list(hist_preds.values()), f, ensure_ascii=False, indent=2)
        
    print("Generating final predictions for upcoming matches...")
    pipeline.predict()
    print("Done!")

if __name__ == "__main__":
    main()
