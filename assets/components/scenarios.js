// assets/components/scenarios.js
import { pct } from '../core/utils.js';

export function scenariosBlock(m,p){
  const sc=p.scenarios;
  if(!sc || !sc.length) return "";
  const col=id=> id==="closed"?"#5b8cff": id==="tight"?"#ffd34e": id==="open"?"#33e0a0":"#ff8a5b";
  const main = sc.filter(s=>!s.angle);
  const angle = sc.filter(s=>s.angle);
  const card = s=>`<div class="scn ${s.angle?"angle":""}">
      <div class="scn-bar" style="background:${col(s.id)}"></div>
      <div class="scn-top"><div class="scn-title">${s.title}</div><div class="scn-p">${pct(s.p)}</div></div>
      <div class="scn-track"><div class="scn-fill" style="width:${Math.round(s.p*100)}%;background:${col(s.id)}"></div></div>
      <div class="scn-scores">${(s.scores||[]).map(x=>`<b>${x}</b>`).join("")}</div>
      <div class="scn-note">${s.note||""}</div>
    </div>`;
  return `<div style="margin-top:14px"><h3>🎬 Scénarios du match</h3>
    <div style="font-size:11.5px;color:var(--muted);margin:2px 0 4px">
      Probabilités dérivées de la grille de scores réelle (les 3 premiers totalisent 100 %).
      « Large écart » est un angle inclus dans « spectacle ».</div>
    <div class="scn-grid">${main.map(card).join("")}</div>
    ${angle.length?`<div class="scn-grid" style="grid-template-columns:1fr">${angle.map(card).join("")}</div>`:""}
  </div>`;
}
