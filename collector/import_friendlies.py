import os
import sys
import json
import requests
import datetime

sys.path.append('.')
from collector.db import database as db
from collector.sources import espn_stats as espn
from collector.sources.espn_stats import _alias

def get_friendlies_from_espn(start_date, end_date):
    url = f'https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.friendly/scoreboard?dates={start_date}-{end_date}&limit=200'
    try:
        res = requests.get(url, timeout=15).json()
        return res.get('events', [])
    except Exception as e:
        print(f"Erreur API ESPN lors de la récupération des amicaux: {e}")
        return []

def main():
    conn = db.init_db()
    
    # 1. Charger les équipes de la base CDM 2026
    wc_teams = {t["name"] for t in db.all_teams(conn)}
    
    # 2. Récupérer les événements
    print("Téléchargement des matchs amicaux de Mars 2026...")
    events = get_friendlies_from_espn('20260315', '20260331')
    print("Téléchargement des matchs amicaux de Juin 2026...")
    events.extend(get_friendlies_from_espn('20260601', '20260613'))
    
    print(f"Total d'événements amicaux récupérés : {len(events)}")
    
    # Éviter les doublons de match (clé unique : home, away, date)
    # Trier par date croissante pour respecter l'ordre chronologique d'insertion
    events.sort(key=lambda x: x.get('date', ''))
    
    def match_team_name(espn_name):
        espn_al = _alias(espn_name)
        for team in wc_teams:
            if espn_al == _alias(team):
                return team
        return None

    imported = 0
    stats_imported = 0
    
    for ev in events:
        if not ev.get('status', {}).get('type', {}).get('completed', False):
            continue
            
        comps = ev.get('competitions', [])
        if not comps: continue
        competitors = comps[0].get('competitors', [])
        if len(competitors) != 2: continue
        
        t1_raw = competitors[0]['team']['name']
        t2_raw = competitors[1]['team']['name']
        
        t1_matched = match_team_name(t1_raw)
        t2_matched = match_team_name(t2_raw)
        
        # On n'importe que si au moins l'une des équipes participe à la CDM 2026
        if not t1_matched and not t2_matched:
            continue
            
        # Si une équipe n'est pas qualifiée CDM, on l'ajoute à la table 'teams'
        # avec un Elo par défaut (1400) pour permettre le traitement dans pipeline.py
        h_name = t1_matched or t1_raw
        a_name = t2_matched or t2_raw
        
        # Déterminer qui est à domicile / extérieur selon l'orientation ESPN
        is_t1_home = competitors[0].get('homeAway') == 'home'
        home = h_name if is_t1_home else a_name
        away = a_name if is_t1_home else h_name
        
        goals_h = int(competitors[0].get('score', '0')) if is_t1_home else int(competitors[1].get('score', '0'))
        goals_a = int(competitors[1].get('score', '0')) if is_t1_home else int(competitors[0].get('score', '0'))
        
        # Formater la date en 'YYYY-MM-DD HH:MM UTC'
        date_raw = ev.get('date', '') # ex: '2026-03-25T12:00Z'
        try:
            dt = datetime.datetime.strptime(date_raw, "%Y-%m-%dT%H:%MZ")
            date_str = dt.strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            date_str = date_raw.replace('T', ' ').replace('Z', ' UTC')
            
        # S'assurer que les équipes existent en base
        for team_name in (home, away):
            db.upsert_team(conn, team_name, elo=1400, fifa_prior=1400)
            
        # Insérer le match dans matches
        cursor = conn.execute("""
            INSERT OR IGNORE INTO matches (competition, stage, utc_date, home, away, status, home_goals, away_goals, processed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, ('Amical', 'Match de préparation', date_str, home, away, 'FINISHED', goals_h, goals_a))
        
        if cursor.rowcount > 0:
            imported += 1
            match_id = cursor.lastrowid
            
            # Récupérer les stats détaillées du match
            summ = espn.match_summary(ev['id'])
            if summ and summ.get('team'):
                t = summ["team"]
                # Déterminer si l'orientation home/away d'ESPN correspond à celle insérée
                espn_home_is_base_home = (t.get("home_name") == home)
                
                def get_stat(base_side, stat_name):
                    espn_side = base_side if espn_home_is_base_home else ("away" if base_side == "home" else "home")
                    return t.get(f"{espn_side}_{stat_name}")
                
                # Ingestion des colonnes standards
                home_xg = get_stat("home", "xg")
                away_xg = get_stat("away", "xg")
                home_shots = get_stat("home", "shots")
                away_shots = get_stat("away", "shots")
                home_shots_on = get_stat("home", "shots_on")
                away_shots_on = get_stat("away", "shots_on")
                home_corners = get_stat("home", "corners")
                away_corners = get_stat("away", "corners")
                home_cards = get_stat("home", "cards")
                away_cards = get_stat("away", "cards")
                
                # Ingestion du score mi-temps
                ht = summ.get("halftime")
                home_ht_goals = None
                away_ht_goals = None
                if ht and "-" in ht:
                    try:
                        parts = ht.split("-")
                        h_ht = int(parts[0])
                        a_ht = int(parts[1])
                        home_ht_goals = h_ht if espn_home_is_base_home else a_ht
                        away_ht_goals = a_ht if espn_home_is_base_home else h_ht
                    except (ValueError, IndexError):
                        pass

                # Ingestion des stats d'équipe complexes sous forme de JSON
                EXT = ["possession", "passes", "passes_ok", "pass_pct", "crosses", "crosses_ok",
                       "long_balls", "tackles", "tackles_won", "interceptions", "clearances",
                       "blocked_shots", "fouls", "offsides", "saves"]
                team_ext = {}
                for side in ("home", "away"):
                    for f in EXT:
                        v = get_stat(side, f)
                        if v is not None:
                            team_ext[f"{side}_{f}"] = v
                ts_json = json.dumps(team_ext, ensure_ascii=False) if team_ext else None
                
                conn.execute("""
                    UPDATE matches SET
                        home_xg=?, away_xg=?, home_shots=?, away_shots=?,
                        home_shots_on=?, away_shots_on=?,
                        home_corners=?, away_corners=?, home_cards=?, away_cards=?,
                        home_ht_goals=?, away_ht_goals=?,
                        team_stats_json=?
                    WHERE id=?
                """, (home_xg, away_xg, home_shots, away_shots, home_shots_on, away_shots_on,
                      home_corners, away_corners, home_cards, away_cards,
                      home_ht_goals, away_ht_goals, ts_json, match_id))
                stats_imported += 1
                
    conn.commit()
    conn.close()
    print(f"✅ {imported} matchs amicaux insérés en base (dont {stats_imported} enrichis de statistiques complètes).")

if __name__ == '__main__':
    main()
