path = r'c:\Users\zakro\ZCodeProject\assets\main.js'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

new_code = '''
  const lamA = nlp.awayLambdaAdj ? `×${nlp.awayLambdaAdj.toFixed(2)}` : "";

  const pens = nlp.penalties;
  let penWarning = "";
  if (pens) {
    const warns = [];
    if (pens.home_adj < 1.0) warns.push(`⚠️ ${m.home} pénalisé (x${pens.home_adj}): ${pens.home_reasons.join(', ')}`);
    if (pens.away_adj < 1.0) warns.push(`⚠️ ${m.away} pénalisé (x${pens.away_adj}): ${pens.away_reasons.join(', ')}`);
    if (warns.length > 0) {
      penWarning = `<div style="margin-bottom:8px;padding:6px;background:rgba(255,60,0,0.15);border:1px solid rgba(255,60,0,0.4);border-radius:4px;font-size:12px;color:#ff8a65;">
        ${warns.join('<br>')}
      </div>`;
    }
  }

  return `
  <div style="margin:14px 0;padding:12px 14px;background:rgba(30,40,60,0.7);border:1px solid rgba(79,195,247,0.25);border-radius:8px;">
    ${penWarning}
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
'''

old_code = '''
  const lamA = nlp.awayLambdaAdj ? `×${nlp.awayLambdaAdj.toFixed(2)}` : "";

  return `
  <div style="margin:14px 0;padding:12px 14px;background:rgba(30,40,60,0.7);border:1px solid rgba(79,195,247,0.25);border-radius:8px;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
'''

text = text.replace(old_code.strip('\n'), new_code.strip('\n'))

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated main.js!')
