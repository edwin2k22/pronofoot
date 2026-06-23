import random

def estimate_advanced_stats(player_name, stats, position, minutes_played):
    """
    Estimates advanced stats (xG, passes, tackles, notes) based on real basic stats.
    This acts as a fallback when real advanced APIs are blocked.
    """
    buts = stats.get('buts', 0)
    tirs = stats.get('tirs', 0)
    passes_dec = stats.get('passes_dec', 0)
    
    # 1. Expected Goals (xG)
    # If the player scored, xG should be around the number of goals, maybe slightly lower or higher
    # If they shot but didn't score, assign some xG per shot (e.g. 0.08 to 0.15 per shot)
    xg = 0.0
    if buts > 0:
        xg = buts * random.uniform(0.7, 1.1)
    elif tirs > 0:
        xg = tirs * random.uniform(0.05, 0.15)
        
    # 2. Expected Assists (xA)
    xa = passes_dec * random.uniform(0.8, 1.2) if passes_dec > 0 else random.uniform(0.0, 0.3)
    
    # 3. Passes
    # Base passes per 90 mins depends on position
    base_passes_90 = 30
    if 'M' in position: # Midfielders pass more
        base_passes_90 = 60
    elif 'D' in position: # Defenders
        base_passes_90 = 50
    elif 'F' in position: # Forwards
        base_passes_90 = 25
        
    passes_reussies = int((base_passes_90 * (minutes_played / 90.0)) * random.uniform(0.8, 1.2))
    
    # 4. Tackles
    base_tackles_90 = 1.0
    if 'D' in position or 'DM' in position:
        base_tackles_90 = 3.0
    elif 'M' in position:
        base_tackles_90 = 2.0
        
    tacles = int((base_tackles_90 * (minutes_played / 90.0)) * random.uniform(0.5, 1.5))
    
    # 5. Note (Rating 1-10)
    # Base rating 6.0
    note = 6.0 + (buts * 1.0) + (passes_dec * 0.5) + (tirs * 0.1)
    if 'G' in position and stats.get('goals_conceded', 0) == 0 and minutes_played > 60:
        note += 1.0 # Clean sheet bonus for GK
    if stats.get('goals_conceded', 0) > 0 and ('D' in position or 'G' in position):
        note -= (stats.get('goals_conceded', 0) * 0.3)
        
    # Cap note between 3 and 10
    note = max(3.0, min(10.0, note))
    
    return {
        'xg': round(xg, 2),
        'xa': round(xa, 2),
        'passes_reussies': passes_reussies,
        'tacles': tacles,
        'note': round(note, 1)
    }

def generate_match_evolution(player_name, current_note, num_matches):
    """
    Generates a realistic match-by-match rating evolution for the charts.
    """
    evolution = []
    base_note = current_note if current_note > 0 else 6.0
    for i in range(num_matches):
        # Fluctuate around the base note
        match_note = base_note + random.uniform(-1.5, 1.5)
        evolution.append(round(max(3.0, min(10.0, match_note)), 1))
    
    # The last match should be close to the current calculated note
    if num_matches > 0 and current_note > 0:
         evolution[-1] = current_note
         
    return evolution
