path = r'c:\Users\zakro\ZCodeProject\collector\models\nlp_momentum.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

new_func = '''
class PenaltySignal(NamedTuple):
    home_penalty_adj: float
    away_penalty_adj: float
    home_reasons: list[str]
    away_reasons: list[str]

def extract_live_penalties(commentary: list[dict], home: str, away: str) -> PenaltySignal:
    """
    Analyse l'historique complet d'un match pour trouver les événements 
    pénalisants majeurs (cartons rouges, blessures).
    """
    if not commentary:
        return PenaltySignal(1.0, 1.0, [], [])
        
    home_l = home.lower()
    away_l = away.lower()
    
    h_adj = 1.0
    a_adj = 1.0
    h_reasons = []
    a_reasons = []
    
    # Parcourt tous les commentaires
    for c in commentary:
        txt = c.get("text", "").lower()
        if not txt: continue
        
        # Carton rouge
        if "red card" in txt:
            if home_l in txt:
                h_adj *= 0.85
                h_reasons.append("Carton rouge (-15%)")
            elif away_l in txt:
                a_adj *= 0.85
                a_reasons.append("Carton rouge (-15%)")
                
        # Blessure
        if "injury" in txt and "delay" in txt:
            if home_l in txt:
                h_adj *= 0.95
                h_reasons.append("Blessure (-5%)")
            elif away_l in txt:
                a_adj *= 0.95
                a_reasons.append("Blessure (-5%)")

    return PenaltySignal(
        home_penalty_adj=round(h_adj, 2),
        away_penalty_adj=round(a_adj, 2),
        home_reasons=h_reasons,
        away_reasons=a_reasons
    )
'''

if 'extract_live_penalties' not in text:
    text += '\n' + new_func

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated nlp_momentum.py')
