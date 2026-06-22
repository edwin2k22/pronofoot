// assets/components/shots.js
import { ouLineRow } from '../core/utils.js';

export function shotsBlock(m,p){
  const s=p.shots; if(!s) return "";
  if(!s.real || s.home==null){
    if(s.expShots==null) return "";
    const ln=s.lines||{}, lnOn=s.linesOn||{};
    const keys=Object.keys(ln).sort((a,b)=>parseFloat(a)-parseFloat(b));
    const keysOn=Object.keys(lnOn).sort((a,b)=>parseFloat(a)-parseFloat(b));
    const rows=keys.map(k=>ouLineRow(`${k} tirs`,ln[k])).join("");
    const rowsOn=keysOn.map(k=>ouLineRow(`${k} cadrés`,lnOn[k])).join("");
    const accBadge=(a)=> a==null?`<span style="color:var(--muted)">N/D</span>`:`${a}%`;
    return `<div class="module mod-shots"><h3>🎯 Tirs & tirs cadrés <span class="mod-hint">📊 prono (moyennes réelles CDM 2026)</span></h3>
      <div class="mod-top">
        <div class="mod-big"><b>${s.expShots}</b><small>tirs projetés</small></div>
        <div class="mod-split">
          <div class="stat"><span>${m.home}</span><span><b>${s.home}</b> tirs · ${s.homeOn} cadrés</span></div>
          <div class="stat"><span>${m.away}</span><span><b>${s.away}</b> tirs · ${s.awayOn} cadrés</span></div>
        </div>
      </div>
      <div class="ou-lines">${rows}</div>
      <div class="mod-big" style="margin-top:10px"><b>${s.expShotsOn}</b><small>tirs cadrés projetés (total)</small></div>
      <div class="ou-lines">${rowsOn}</div>
      ${(s.shotsAvgHome!=null||s.shotsAvgAway!=null)?`<div class="stat"><span>Tirs moy. (réel)</span><span>${s.shotsAvgHome??"N/D"} — ${s.shotsAvgAway??"N/D"}</span></div>`:""}
      <div class="stat"><span>Précision attendue ${m.home}</span><span>${accBadge(s.homeAcc)}</span></div>
      <div class="stat"><span>Précision attendue ${m.away}</span><span>${accBadge(s.awayAcc)}</span></div>
      ${s.basis?`<div class="note" style="margin-top:8px">📐 Calculé sur : <b>attaque/défense</b> (tirs produits vs concédés) × <b>domination</b> (${s.basis.dominance?.[0]}/${s.basis.dominance?.[1]}, via buts attendus + Elo) × <b>possession</b> (${s.basis.possession?.[0]}%/${s.basis.possession?.[1]}%). Cadrés = tirs × précision réelle de chaque équipe (${s.basis.accuracy?.[0]}%/${s.basis.accuracy?.[1]}%).</div>`:`<div class="note" style="margin-top:8px">Projection dérivée des tirs réellement produits/concédés par chaque sélection au Mondial 2026.</div>`}
      <div class="note" style="margin-top:4px;opacity:.75">⚠️ Les tirs d'un match sont très variables : ce prono indique une tendance, pas une certitude.</div>
    </div>`;
  }
  const tot=Math.max((s.home||0)+(s.away||0),1);
  const hW=Math.round((s.home||0)/tot*100);
  const totOn=Math.max((s.homeOn||0)+(s.awayOn||0),1);
  const hOnW=Math.round((s.homeOn||0)/totOn*100);
  const accBadge=(a)=> a==null?`<span style="color:var(--muted)">N/D</span>`:`${a}%`;
  return `<div class="module mod-shots"><h3>🎯 Tirs & tirs cadrés <span class="mod-hint">données réelles du match</span></h3>
    <div class="cmp">
      <div class="cmp-lbl"><b>${s.home}</b><span>Tirs</span><b>${s.away}</b></div>
      <div class="cmp-bar"><span class="cmp-h" style="width:${hW}%"></span><span class="cmp-a" style="width:${100-hW}%"></span></div>
    </div>
    <div class="cmp">
      <div class="cmp-lbl"><b>${s.homeOn??"N/D"}</b><span>Tirs cadrés</span><b>${s.awayOn??"N/D"}</b></div>
      <div class="cmp-bar"><span class="cmp-h on" style="width:${hOnW}%"></span><span class="cmp-a on" style="width:${100-hOnW}%"></span></div>
    </div>
    <div class="stat"><span>Précision ${m.home}</span><span>${accBadge(s.homeAcc)}</span></div>
    <div class="stat"><span>Précision ${m.away}</span><span>${accBadge(s.awayAcc)}</span></div>
  </div>`;
}
