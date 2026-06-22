// assets/components/corners.js
import { pct, ouLineRow } from '../core/utils.js';

export function cornersBlock(m,p){
  const c=p.corners; if(!c) return "";
  const ln=c.lines||{};
  const keys=Object.keys(ln).sort((a,b)=>parseFloat(a)-parseFloat(b));
  const rows=keys.map(k=>ouLineRow(`${k} corners`,ln[k])).join("");
  return `<div class="module mod-corners"><h3>⛳ Corners ${c.src?`<span class="mod-hint">📊 ${c.src}</span>`:""}</h3>
    <div class="mod-top">
      <div class="mod-big"><b>${c.exp_corners}</b><small>total projeté</small></div>
      <div class="mod-split">
        <div class="stat"><span>${m.home}</span><span><b>${c.home}</b></span></div>
        <div class="stat"><span>${m.away}</span><span><b>${c.away}</b></span></div>
      </div>
    </div>
    <div class="ou-wrap">
      <div class="ou-legend"><span><i class="dot u"></i>Under</span><span>50%</span><span><i class="dot o"></i>Over</span></div>
      ${rows}
    </div></div>`;
}
