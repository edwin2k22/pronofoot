import json
import requests
import sys

# Charger _alias depuis espn_stats pour réutiliser la même logique
sys.path.append('.')
from collector.sources.espn_stats import _alias, _tok_set

def get_friendlies_from_espn(start_date, end_date):
    url = f'https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.friendly/scoreboard?dates={start_date}-{end_date}&limit=200'
    try:
        res = requests.get(url, timeout=10).json()
        return res.get('events', [])
    except Exception as e:
        print(f"Erreur API ESPN: {e}")
        return []

def main():
    path_form = 'collector/data/recent_form.json'
    with open(path_form, 'r', encoding='utf-8') as f:
        form_data = json.load(f)
    
    # Créer un dictionnaire inversé pour trouver le nom interne à partir de l'alias
    # Ou bien, on peut simplement tester tous les noms internes
    internal_teams = list(form_data.keys())
    
    def match_team_name(espn_name):
        espn_al = _alias(espn_name)
        espn_tok = _tok_set(espn_name)
        
        for team in internal_teams:
            if espn_al == _alias(team):
                return team
        
        # Test tokens
        for team in internal_teams:
            internal_tok = _tok_set(team)
            if espn_tok & internal_tok == espn_tok or espn_tok & internal_tok == internal_tok:
                # Éviter les faux positifs trop courts (ex: South Africa vs South Korea)
                # Mais en général, pour ces pays, _alias gère.
                if len(espn_tok & internal_tok) >= max(len(espn_tok), len(internal_tok)) - 1:
                    return team
        return None

    events = []
    print("Fetching March 2026 friendlies...")
    events.extend(get_friendlies_from_espn('20260315', '20260331'))
    print("Fetching June 2026 friendlies...")
    events.extend(get_friendlies_from_espn('20260601', '20260613'))
    
    # Pour dédupliquer, on stocke "Equipe vs Adversaire" ou bien le nom de l'adversaire
    
    updated_count = 0
    
    # Traitement chronologique ou inverse (on insérera au début de la liste)
    # L'API renvoie souvent dans l'ordre chronologique. Si on veut que le plus récent soit à l'index 0,
    # il faut insérer à l'envers ou bien d'abord tout collecter et trier par date décroissante.
    # On va trier par date décroissante :
    events.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    for ev in events:
        if ev.get('status', {}).get('type', {}).get('completed', False):
            comps = ev.get('competitions', [])
            if not comps: continue
            competitors = comps[0].get('competitors', [])
            if len(competitors) != 2: continue
            
            t1 = competitors[0]
            t2 = competitors[1]
            
            name1 = match_team_name(t1['team']['name'])
            name2 = match_team_name(t2['team']['name'])
            
            score1 = int(t1.get('score', '0'))
            score2 = int(t2.get('score', '0'))
            
            def determine_res(s1, s2):
                if s1 > s2: return "W"
                if s1 < s2: return "L"
                return "D"
            
            venue1 = "H" if t1.get('homeAway') == 'home' else "A"
            venue2 = "H" if t2.get('homeAway') == 'home' else "A"
            
            # Neutral site ?
            if comps[0].get('neutralSite'):
                venue1 = "N"
                venue2 = "N"
            
            def add_match(team_name, opponent_raw, goals_scored, goals_conceded, venue):
                if not team_name: return
                res = determine_res(goals_scored, goals_conceded)
                
                # Check if already present to avoid duplicates
                # We assume if the opponent and result matches the first few entries, it's a dup.
                # Since we prepended things, let's check the whole list just in case.
                opp_alias = _alias(opponent_raw)
                
                is_dup = False
                for existing in form_data[team_name]:
                    if _alias(existing[0]) == opp_alias and existing[5] == "Amical" and existing[2] == goals_scored and existing[3] == goals_conceded:
                        is_dup = True
                        break
                
                if not is_dup:
                    print(f"Adding match for {team_name}: vs {opponent_raw} ({goals_scored}-{goals_conceded})")
                    form_data[team_name].insert(0, [
                        opponent_raw,
                        venue,
                        goals_scored,
                        goals_conceded,
                        res,
                        "Amical"
                    ])
                    return True
                return False

            if add_match(name1, t2['team']['name'], score1, score2, venue1):
                updated_count += 1
            if add_match(name2, t1['team']['name'], score2, score1, venue2):
                updated_count += 1
                
    if updated_count > 0:
        with open(path_form, 'w', encoding='utf-8') as f:
            json.dump(form_data, f, indent=2, ensure_ascii=False)
        print(f"✅ {updated_count} nouveaux matchs amicaux intégrés à la base !")
    else:
        print("Aucun nouveau match à ajouter.")

if __name__ == '__main__':
    main()
