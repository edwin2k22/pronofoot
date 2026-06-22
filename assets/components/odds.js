// assets/components/odds.js

export function oddsBlock(m,p){
  if(m.odd1==null) return "";
  const v=p.value||{}, k=p.kelly||{};
  const lm=p.lineMovement;
  const cell=(lbl,odd,val,kel)=>{
    const isVal = val&&val.value;
    const kpct = (kel&&kel.kelly)?` · 💰 ${Math.round(kel.kelly*100)}%`:"";
    return `<div class="odd-cell ${isVal?'val':''}">
      <div class="odd-lbl">${lbl}</div>
      <div class="odd-val">${odd!=null?odd.toFixed(2):"—"}</div>
      <div class="odd-edge">${val?(val.edge>0?'+':'')+Math.round(val.edge*100)+' pts':''}${isVal?' ✅':''}${kpct}</div>
    </div>`;
  };
  let mv="";
  if(lm && lm.opening){
    const arrow=x=> (x!=null&&x<-0.05)?'📉':(x!=null&&x>0.05?'📈':'➡️');
    const op=lm.opening;
    mv=`<div class="odd-mv">Mouvement cote : ${m.home} ${arrow(lm.home)} · ${m.away} ${arrow(lm.away)} <span style="color:var(--muted)">(ouverture ${op.odd1}/${op.oddX}/${op.odd2})</span></div>`;
  }
  return `<div class="module mod-odds"><h3>🎰 Cotes & value <span class="mod-hint">${m.oddsProvider||"bookmaker"} · réelles</span></h3>
    <div class="odd-grid">
      ${cell(m.home, m.odd1, v.home, k.home)}
      ${cell("Nul", m.oddX, v.draw, k.draw)}
      ${cell(m.away, m.odd2, v.away, k.away)}
    </div>
    ${mv}
    <div class="odd-note">✅ value = le modèle estime une probabilité supérieure à celle du bookmaker (+2 pts mini). 💰 = mise Kelly conseillée (% bankroll, plafonné 5%). <b>Information, pas un conseil de pari.</b></div>
  </div>`;
}
