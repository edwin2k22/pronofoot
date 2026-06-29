import re

path = r'c:\Users\zakro\ZCodeProject\collector\pipeline.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

new_code = '''
                    _sig = nlpm.analyse_commentary(
                        _comments, mt["home"], mt["away"],
                        current_minute=_cur_min, window_size=20
                    )
                    _pen = nlpm.extract_live_penalties(_comments, mt["home"], mt["away"])
                    
                    # Appliquer d'abord la pénalité structurelle
                    lam_h = lam_h * _pen.home_penalty_adj
                    lam_a = lam_a * _pen.away_penalty_adj
                    
                    # Appliquer les multiplicateurs λ (effet NLP plafonné à ±20%)
                    _nlp_h = max(0.80, min(1.20, _sig.home_lambda_adj))
                    _nlp_a = max(0.80, min(1.20, _sig.away_lambda_adj))
                    lam_h = round(max(0.2, lam_h * _nlp_h), 2)
                    lam_a = round(max(0.2, lam_a * _nlp_a), 2)
                    
                    nlp_signal = nlpm.momentum_to_dict(_sig)
                    nlp_signal['penalties'] = {
                        'home_adj': _pen.home_penalty_adj,
                        'away_adj': _pen.away_penalty_adj,
                        'home_reasons': _pen.home_reasons,
                        'away_reasons': _pen.away_reasons
                    }
'''

old_code = '''
                    _sig = nlpm.analyse_commentary(
                        _comments, mt["home"], mt["away"],
                        current_minute=_cur_min, window_size=20
                    )
                    # Appliquer les multiplicateurs λ (effet NLP plafonné à ±20%)
                    _nlp_h = max(0.80, min(1.20, _sig.home_lambda_adj))
                    _nlp_a = max(0.80, min(1.20, _sig.away_lambda_adj))
                    lam_h = round(max(0.2, lam_h * _nlp_h), 2)
                    lam_a = round(max(0.2, lam_a * _nlp_a), 2)
                    nlp_signal = nlpm.momentum_to_dict(_sig)
'''

text = text.replace(old_code.strip('\n'), new_code.strip('\n'))

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated pipeline.py!')
