import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('collector/data/predictions.json', encoding='utf-8') as f:
    matches = json.load(f)

print('| Match | Marché | Prono Value | Cote | Résultat | Edge |')
print('|---|---|---|---|---|---|')

wins = 0
losses = 0
pnl = 0.0

for m in matches:
    if m.get('status') != 'FINISHED' or not m.get('analysis'): continue
    
    p = m['prediction']
    a = m['analysis']
    try:
        hg, ag = map(int, a['realScore'].split('-'))
    except Exception:
        continue
        
    # 1N2
    if m.get('odd1') and m.get('oddX') and m.get('odd2'):
        outcome = '1' if hg > ag else ('2' if ag > hg else 'X')
        for k, odd in (('1', m['odd1']), ('X', m['oddX']), ('2', m['odd2'])):
            pm = {'1': p['p1'], 'X': p['pX'], '2': p['p2']}[k]
            edge = pm - 1.0/odd
            if edge > 0:
                won = (k == outcome)
                if won: 
                    wins += 1; pnl += (odd - 1)
                else: 
                    losses += 1; pnl -= 1
                res_icon = '✅' if won else '❌'
                prono_label = {'1': m['home'], 'X': 'Nul', '2': m['away']}[k]
                profit = f"+{(odd - 1):.2f}u" if won else "-1.00u"
                print(f'| {m["home"]} vs {m["away"]} | 1N2 | {prono_label} | {odd} | {res_icon} ({profit}) | +{edge*100:.1f}% |')

    # Over/Under
    if m.get('oddOU_line') and m.get('oddOver') and m.get('oddUnder'):
        ou_line = m['oddOU_line']
        if str(ou_line) in p.get('overUnder', {}):
            ou_probs = p['overUnder'][str(ou_line)]
            real_total = hg + ag
            for k, odd, label in (('over', m['oddOver'], f'Plus {ou_line}'), ('under', m['oddUnder'], f'Moins {ou_line}')):
                pm = ou_probs[k]
                edge = pm - 1.0/odd
                if edge > 0:
                    if k == 'over': won = (real_total > ou_line)
                    else: won = (real_total < ou_line)
                    
                    if won: 
                        wins += 1; pnl += (odd - 1)
                    else: 
                        losses += 1; pnl -= 1
                        
                    res_icon = '✅' if won else '❌'
                    profit = f"+{(odd - 1):.2f}u" if won else "-1.00u"
                    print(f'| {m["home"]} vs {m["away"]} | O/U | {label} | {odd} | {res_icon} ({profit}) | +{edge*100:.1f}% |')

    # BTTS
    if m.get('oddBTTS_Yes') and m.get('oddBTTS_No') and 'btts' in p:
        btts_real = (hg > 0 and ag > 0)
        for k, odd, label in (('yes', m['oddBTTS_Yes'], 'BTTS: Oui'), ('no', m['oddBTTS_No'], 'BTTS: Non')):
            pm = p['btts'] if k == 'yes' else (1 - p['btts'])
            edge = pm - 1.0/odd
            if edge > 0:
                won = (btts_real if k == 'yes' else not btts_real)
                if won: 
                    wins += 1; pnl += (odd - 1)
                else: 
                    losses += 1; pnl -= 1
                    
                res_icon = '✅' if won else '❌'
                profit = f"+{(odd - 1):.2f}u" if won else "-1.00u"
                print(f'| {m["home"]} vs {m["away"]} | BTTS | {label} | {odd} | {res_icon} ({profit}) | +{edge*100:.1f}% |')

print(f'\n**Bilan Global :** {wins} gagnés, {losses} perdus. Total paris: {wins+losses} | PnL: {pnl:+.2f} unités (Yield: {pnl/(wins+losses)*100:+.1f}%)')
