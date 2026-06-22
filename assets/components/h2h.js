// assets/components/h2h.js
import { H2H } from '../core/state.js';

export function h2hBlock(m){
  const h = H2H[m.home+"|"+m.away] || H2H[m.away+"|"+m.home];
  if(!h || !h.games || !h.games.length) return "";
  const s=h.summary||{};
  
  const flip = !H2H[m.home+"|"+m.away];
  const win = flip ? s.loss : s.win, loss = flip ? s.win : s.loss, draw=s.draw;
  const rows=h.games.slice(0,6).map(g=>{
    let sc=g.score;
    if(flip) sc = sc.split("-").reverse().join("-");
    const [a,b]=sc.split("-").map(Number);
    const col = a>b?"var(--acc)":(a<b?"var(--danger)":"var(--muted)");
    return `<div class="h2h-row"><span class="h2h-d">${g.date||""}</span>
      <span class="h2h-sc" style="color:${col}">${sc}</span>
      <span class="h2h-c">${g.competition||""}</span></div>`;
  }).join("");
  return `<div class="module"><h3>🤝 Confrontations directes <span class="mod-hint">historique réel ESPN</span></h3>
    <div class="h2h-sum">
      <div><b style="color:var(--acc)">${win}</b><small>${m.home}</small></div>
      <div><b>${draw}</b><small>nuls</small></div>
      <div><b style="color:var(--danger)">${loss}</b><small>${m.away}</small></div>
    </div>
    <div class="h2h-list">${rows}</div>
    <div class="note" style="margin-top:6px">Scores du point de vue de <b>${m.home}</b> · ${s.total} match(s) recensés.</div>
  </div>`;
}
